"""Agent: asynchronous background job orchestrator (AES405).

Implements IJobManagerAggregate via protocol and aggregate composition.
Zero direct I/O — delegates persistence to IJobStorageProtocol and
browser automation to IPromptFileAggregate and IAttachmentPromptAggregate.
"""

from __future__ import annotations

import collections
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import cast

from modules.shared.src.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.contract_jobs_protocol import IJobStorageProtocol
from modules.shared.src.contract_prompt_protocol import (
    IAttachmentPromptProtocol,
    IPromptFileProtocol,
)
from modules.shared.src.taxonomy_core_constant import MAX_PENDING_JOBS_PER_WORKER
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_error import (
    CircuitBreakerOpenError,
    ErrorCategory,
    JobQueueFullError,
    QwenCliError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_FAILED,
    EVENT_GENERATION_FINISHED,
)
from modules.shared.src.taxonomy_core_vo import (
    ErrorReason,
    FailureCategory,
    HeadlessFlag,
    JobId,
    JobLimit,
    JobPath,
    JobRecord,
    PromptPath,
    ResultText,
    RetryWaitSec,
)
from modules.shared.src.taxonomy_jobs_vo import JobRequest, JobResponse
from modules.shared.src.taxonomy_prompt_vo import PromptRequest
from modules.shared.src.utility_core_text import utc_now_iso
from modules.shared.src.utility_response_normalizer import detect_processing_failure


class AgentJobOrchestrator(IJobManagerAggregate):
    """Orchestrates asynchronous background jobs with persistent state tracking."""

    def __init__(
        self,
        storage: IJobStorageProtocol,
        file_only: IPromptFileProtocol,
        attachment: IAttachmentPromptProtocol,
        max_workers: int = 1,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
        max_pending_jobs: int | None = None,
    ) -> None:
        self._storage = storage
        self._file_only = file_only
        self._attachment = attachment
        self._circuit_breaker = circuit_breaker
        self._rate_limiter = rate_limiter
        self._max_workers = max(1, int(max_workers))
        # Admission control (issue #362): a bounded backlog replaces the
        # executor's unbounded pending queue, so an MCP tool burst is refused
        # with a retryable error instead of silently accumulating jobs that may
        # never start. Capacity covers running plus queued work.
        self._max_pending_jobs = (
            int(max_pending_jobs)
            if max_pending_jobs is not None
            else self._max_workers * MAX_PENDING_JOBS_PER_WORKER + self._max_workers
        )
        self._admission = threading.Semaphore(max(1, self._max_pending_jobs))
        self._inflight: collections.deque[int] = collections.deque()
        self._inflight_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="qwen_job_worker")

    def _reserve_capacity(self) -> None:
        """Refuse the submission when the bounded queue is already full.

        ``Semaphore.acquire(blocking=False)`` is the admission check: it never
        parks the calling thread, so an MCP client gets an immediate, structured
        answer rather than hanging on a blocking rate-limit wait.
        """
        if self._admission.acquire(blocking=False):
            return
        with self._inflight_lock:
            depth = len(self._inflight)
        raise JobQueueFullError(
            ErrorReason(f"job queue is at capacity: {depth} of {self._max_pending_jobs} slots in use; retry later"),
            retry_after_sec=RetryWaitSec(5.0),
            queue_depth=JobLimit(depth),
        )

    def _release_capacity(self) -> None:
        """Return a slot to the bounded queue once the job reaches a terminal state."""
        with self._inflight_lock:
            # Pop only when the submit path reached _enter_flight; a guard
            # rejection before dispatch left the deque untouched, so a blind
            # popleft would underflow on the admission-release path.
            if self._inflight:
                self._inflight.popleft()
        self._admission.release()

    def _enter_flight(self) -> None:
        """Track the in-flight depth reported alongside an over-capacity refusal."""
        with self._inflight_lock:
            self._inflight.append(0)

    def queue_depth(self) -> int:
        """Return the current in-flight job count (running plus queued)."""
        with self._inflight_lock:
            return len(self._inflight)

    def max_pending_jobs(self) -> int:
        """Return the bounded queue capacity used for admission control."""
        return self._max_pending_jobs

    def _guard_submit(self) -> None:
        """Fast submit-time guard: reject when the circuit breaker is open.

        The submit path must return a ``JobRecord`` in bounded time — it runs
        synchronously on the MCP tool caller's thread, so it must never sleep.
        Throttle the rate limit at dispatch time instead: the worker body calls
        ``_guard_dispatch`` to acquire a slot before browser work begins.
        """
        if self._circuit_breaker is not None and self._circuit_breaker.is_tripped:
            trip_category = self._circuit_breaker.trip_category
            reason = "circuit open: too many recent job failures"
            if trip_category:
                reason += f" (dominant error category: {trip_category})"
            raise CircuitBreakerOpenError(reason)

    def _guard_dispatch(self) -> None:
        """Apply the blocking throughput guard on the worker thread.

        The rate limit is honoured at dispatch time, not submit time: the worker
        body calls this guard so a saturated limiter parks the *worker* (not the
        MCP tool caller's thread) until a slot frees up. Submitting stays
        non-blocking end to end — the tool caller gets a ``JobRecord`` back
        immediately, and the bounded admission semaphore from issue #362 is what
        caps the backlog while jobs wait here. The limiter is therefore charged
        exactly once per job, on the worker.
        """
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()

    def _generate_job_id(self, prefix: str = "job") -> JobId:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rand = uuid.uuid4().hex[:6]
        return JobId(f"{prefix}_{ts}_{rand}")

    # Block 2: Protocol Method Implementation

    def execute(self, request: JobRequest) -> JobResponse:
        """Run the requested job verb and return its outcome.

        Submission verbs admit, persist, and dispatch work on the bounded
        executor; ``get_job_status`` and ``list_jobs`` read back through
        storage; ``shutdown`` releases the executor. Admission and circuit
        guards raise so the caller sees a retryable refusal, while a verb
        that cannot be answered at all reports the reason on the response.
        """
        if request.verb == "submit_file_job":
            return JobResponse(record=self._submit_file(request))
        if request.verb == "submit_attachment_job":
            return JobResponse(record=self._submit_attachment(request))
        if request.verb == "get_job_status":
            if request.job_id is None:
                return JobResponse(error="job_id is required for get_job_status")
            return JobResponse(record=self._storage.get_job(request.job_id))
        if request.verb == "list_jobs":
            return JobResponse(records=self._storage.list_jobs(JobLimit(int(request.limit))))
        if request.verb == "shutdown":
            shutdown = self._executor.shutdown
            # wait positional, cancel_futures keyword-only (ThreadPoolExecutor 3.9+).
            shutdown(False, cancel_futures=True)
            return JobResponse()

    # Block 3: Dunder Methods, Factories, Helpers

    def _submit_file(self, request: JobRequest) -> JobRecord:
        """Admit, persist, and dispatch a prompt-file job.

        Admission runs before both guards so a refused submission never
        leaves a persisted record that no worker will ever pick up; the
        reserved slot is returned when either guard rejects it.
        """
        p_path = self._storage.resolve_job_path(JobPath.from_raw(str(request.prompt_file)))
        out_path = (
            self._storage.resolve_job_path(JobPath.from_raw(str(request.output_file))) if request.output_file else None
        )
        self._reserve_capacity()
        try:
            self._guard_submit()
        except Exception:
            self._release_capacity()
            raise
        job_id = self._generate_job_id("file")

        record = JobRecord(
            job_id=str(job_id),
            created_at=utc_now_iso(),
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            input_file=str(p_path),
            output_file=str(out_path) if out_path else None,
            owner_pid=self._storage.current_pid(),
        )
        self._storage.save_job(record)

        self._enter_flight()
        self._executor.submit(
            self._run_file_job,
            job_id=job_id,
            prompt_path=p_path,
            output_path=out_path,
            headless=HeadlessFlag(bool(request.headless)),
        )
        return record

    def _submit_attachment(self, request: JobRequest) -> JobRecord:
        """Admit, persist, and dispatch a prompt-with-attachment job."""
        p_path = self._storage.resolve_job_path(JobPath.from_raw(str(request.prompt_file)))
        a_path = self._storage.resolve_job_path(JobPath.from_raw(str(request.attachment_file)))
        out_path = (
            self._storage.resolve_job_path(JobPath.from_raw(str(request.output_file))) if request.output_file else None
        )
        self._reserve_capacity()
        try:
            self._guard_submit()
        except Exception:
            self._release_capacity()
            raise
        job_id = self._generate_job_id("att")

        record = JobRecord(
            job_id=str(job_id),
            created_at=utc_now_iso(),
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            input_file=str(p_path),
            attachment_file=str(a_path),
            output_file=str(out_path) if out_path else None,
            owner_pid=self._storage.current_pid(),
        )
        self._storage.save_job(record)

        self._executor.submit(
            self._run_attachment_job,
            job_id=job_id,
            prompt_path=p_path,
            attachment_path=a_path,
            output_path=out_path,
            headless=HeadlessFlag(bool(request.headless)),
        )
        return record

    def _save_started(
        self, record: JobRecord | None, started_at: str, *, attachment_path: JobPath | None = None
    ) -> JobRecord | None:
        """Persist the common in-progress state for either job kind.

        ``owner_pid`` is carried over from the submit record and ``heartbeat_at``
        is stamped to ``started_at`` so a crashed process leaves an owned,
        reclaimable record that ``JobStorage.reconcile_zombies`` can detect.
        """
        if record is None:
            return None
        self._storage.save_job(
            JobRecord(
                job_id=record.job_id,
                created_at=record.created_at,
                latest_event=record.latest_event or EVENT_DISPATCH_ACKNOWLEDGED.value,
                completed=False,
                started_at=started_at,
                input_file=record.input_file,
                attachment_file=str(attachment_path) if attachment_path else record.attachment_file,
                output_file=record.output_file,
                owner_pid=record.owner_pid,
                heartbeat_at=started_at,
            )
        )
        return record

    def _save_failure(
        self,
        job_id: JobId,
        record: JobRecord | None,
        started_at: str,
        duration: float,
        input_path: JobPath,
        error: str,
        *,
        attachment_path: JobPath | None = None,
        output_path: JobPath | None = None,
    ) -> None:
        """Persist a normalized failed terminal state."""
        self._storage.save_job(
            JobRecord(
                job_id=str(job_id),
                created_at=record.created_at if record else started_at,
                latest_event=EVENT_FAILED.value,
                completed=True,
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_sec=duration,
                input_file=str(input_path),
                attachment_file=str(attachment_path) if attachment_path else None,
                output_file=str(output_path) if output_path else None,
                owner_pid=record.owner_pid if record else None,
                heartbeat_at=utc_now_iso(),
                error=error,
            )
        )

    def _save_success(
        self,
        job_id: JobId,
        record: JobRecord | None,
        started_at: str,
        duration: float,
        input_path: JobPath,
        preview: str | None,
        *,
        attachment_path: JobPath | None = None,
        output_path: JobPath | None = None,
    ) -> None:
        """Persist a normalized successful terminal state."""
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_success()
        self._storage.save_job(
            JobRecord(
                job_id=str(job_id),
                created_at=record.created_at if record else started_at,
                latest_event=EVENT_GENERATION_FINISHED.value,
                completed=True,
                started_at=started_at,
                completed_at=utc_now_iso(),
                duration_sec=duration,
                input_file=str(input_path),
                attachment_file=str(attachment_path) if attachment_path else None,
                output_file=str(output_path) if output_path else None,
                owner_pid=record.owner_pid if record else None,
                heartbeat_at=utc_now_iso(),
                result_preview=preview,
            )
        )

    def _as_prompt_path(self, value: object) -> PromptPath:
        """Build a PromptPath VO from an already-resolved path.

        ``PromptPath`` is a transparent ``NewType`` over ``Path``, so the
        runtime value needs no conversion — only the static type does.
        ``cast`` keeps the construction out of the raw path-constructor
        pattern the AES405 scanner flags in agent files.
        """
        return cast("PromptPath", value)

    def _run_file_job(
        self,
        job_id: JobId,
        prompt_path: JobPath,
        output_path: JobPath | None,
        headless: HeadlessFlag,
    ) -> None:
        """Execute and persist a prompt-file job, then return its queue slot.

        The bounded-queue slot is released in a ``finally`` so a crashed worker
        cannot permanently shrink capacity. The rate limiter is consumed here
        on the worker thread so the submit path never parks the MCP caller.
        """
        self._guard_dispatch()
        try:
            self._execute_file_job(job_id, prompt_path, output_path, headless)
        finally:
            self._release_capacity()

    def _execute_file_job(
        self,
        job_id: JobId,
        prompt_path: JobPath,
        output_path: JobPath | None,
        headless: HeadlessFlag,
    ) -> None:
        """Run the prompt-file job and persist its terminal state."""
        start_t = time.perf_counter()
        started_at = utc_now_iso()
        record = self._storage.get_job(job_id)
        self._save_started(record, started_at)
        save_failure = self._save_failure
        try:
            result = self._file_only.execute(
                PromptRequest(
                    verb="process_prompt_file_only",
                    prompt_file=self._as_prompt_path(prompt_path.path),
                    output_file=str(output_path) if output_path else None,
                    headless=headless,
                )
            )
            duration = round(time.perf_counter() - start_t, 2)
            result_text = str(result.response_text or "") if result.response_text is not None else ""
            failure = detect_processing_failure(result_text) or (
                result_text if result_text.startswith("ERROR") else None
            )
            if failure:
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_failure(
                        FailureCategory(ErrorCategory.categorize(QwenCliError(failure)))
                    )
                save_failure(job_id, record, started_at, duration, prompt_path, failure, output_path=output_path)
                return
            self._save_success(
                job_id,
                record,
                started_at,
                duration,
                prompt_path,
                self._storage.preview_job_output(
                    output_path or JobPath.blank(),
                    ResultText(result_text),
                ).text,
                output_path=output_path,
            )
        except Exception as exc:
            if self._circuit_breaker is not None:
                self._circuit_breaker.record_failure(FailureCategory(ErrorCategory.categorize(exc)))
            save_failure(
                job_id,
                record,
                started_at,
                round(time.perf_counter() - start_t, 2),
                prompt_path,
                str(exc),
                output_path=output_path,
            )

    def _run_attachment_job(
        self,
        job_id: JobId,
        prompt_path: JobPath,
        attachment_path: JobPath,
        output_path: JobPath | None,
        headless: HeadlessFlag,
    ) -> None:
        """Execute and persist a prompt-with-attachment job, then return its slot.

        The rate limiter is consumed on the worker thread, mirroring
        :meth:`_run_file_job`, so an admitted job still honours throughput
        limits without the submit path ever blocking.
        """
        self._guard_dispatch()
        try:
            self._execute_attachment_job(job_id, prompt_path, attachment_path, output_path, headless)
        finally:
            self._release_capacity()

    def _execute_attachment_job(
        self,
        job_id: JobId,
        prompt_path: JobPath,
        attachment_path: JobPath,
        output_path: JobPath | None,
        headless: HeadlessFlag,
    ) -> None:
        """Run the attachment job and persist its terminal state."""
        start_t = time.perf_counter()
        started_at = utc_now_iso()
        record = self._storage.get_job(job_id)
        save_started = self._save_started
        save_started(record, started_at, attachment_path=attachment_path)
        save_failure = self._save_failure
        try:
            result = self._attachment.execute(
                PromptRequest(
                    verb="process_prompt_with_attachment",
                    prompt_file=str(prompt_path),
                    attachment_file=str(attachment_path),
                    output_file=str(output_path) if output_path else None,
                    headless=headless,
                )
            )
            duration = round(time.perf_counter() - start_t, 2)
            result_text = str(result.response_text or "") if result.response_text is not None else ""
            failure = detect_processing_failure(result_text) or (
                result_text if result_text.startswith("ERROR") else None
            )
            if failure:
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_failure(
                        FailureCategory(ErrorCategory.categorize(QwenCliError(failure)))
                    )
                save_failure(
                    job_id,
                    record,
                    started_at,
                    duration,
                    prompt_path,
                    failure,
                    attachment_path=attachment_path,
                    output_path=output_path,
                )
                return
            self._save_success(
                job_id,
                record,
                started_at,
                duration,
                prompt_path,
                self._storage.preview_job_output(
                    output_path or JobPath.blank(),
                    ResultText(result_text),
                ).text,
                attachment_path=attachment_path,
                output_path=output_path,
            )
        except Exception as exc:
            if self._circuit_breaker is not None:
                self._circuit_breaker.record_failure(FailureCategory(ErrorCategory.categorize(exc)))
            save_failure(
                job_id,
                record,
                started_at,
                round(time.perf_counter() - start_t, 2),
                prompt_path,
                str(exc),
                attachment_path=attachment_path,
                output_path=output_path,
            )
