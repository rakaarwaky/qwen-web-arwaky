"""Agent: asynchronous background job orchestrator (AES405).

Implements IJobManagerAggregate via protocol and aggregate composition.
Zero direct I/O — delegates persistence to IJobStorageProtocol and
browser automation to IPromptFileAggregate and IAttachmentPromptAggregate.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
)
from modules.shared.src.contract_core_protocol import IJobStorageProtocol
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
)
from modules.shared.src.taxonomy_core_vo import (
    AttachmentPath,
    FilePath,
    HeadlessFlag,
    JobId,
    JobRecord,
    OutputPath,
    PromptPath,
)
from modules.shared.src.utility_core_response import detect_processing_failure


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentJobOrchestrator(IJobManagerAggregate):
    """Orchestrates asynchronous background jobs with persistent state tracking."""

    def __init__(
        self,
        storage: IJobStorageProtocol,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        max_workers: int = 1,
    ) -> None:
        self._storage = storage
        self._file_only = file_only
        self._attachment = attachment
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="qwen_job_worker")

    def _generate_job_id(self, prefix: str = "job") -> JobId:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rand = uuid.uuid4().hex[:6]
        return JobId(f"{prefix}_{ts}_{rand}")

    def submit_file_job(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> JobRecord:
        """Submit a prompt file job for asynchronous background processing."""
        p_path = Path(prompt_file).expanduser().resolve()
        out_path = Path(output_file).expanduser().resolve() if output_file else None
        job_id = self._generate_job_id("file")
        now = _utc_now_iso()

        record = JobRecord(
            job_id=str(job_id),
            created_at=now,
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            input_file=str(p_path),
            output_file=str(out_path) if out_path else None,
        )
        self._storage.save_job(record)

        self._executor.submit(
            self._run_file_job,
            job_id=job_id,
            prompt_path=p_path,
            output_path=out_path,
            headless=headless,
        )
        return record

    def submit_attachment_job(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> JobRecord:
        """Submit a prompt with attachment job for asynchronous background processing."""
        p_path = Path(prompt_file).expanduser().resolve()
        a_path = Path(attachment_file).expanduser().resolve()
        out_path = Path(output_file).expanduser().resolve() if output_file else None
        job_id = self._generate_job_id("att")
        now = _utc_now_iso()

        record = JobRecord(
            job_id=str(job_id),
            created_at=now,
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            input_file=str(p_path),
            attachment_file=str(a_path),
            output_file=str(out_path) if out_path else None,
        )
        self._storage.save_job(record)

        self._executor.submit(
            self._run_attachment_job,
            job_id=job_id,
            prompt_path=p_path,
            attachment_path=a_path,
            output_path=out_path,
            headless=headless,
        )
        return record

    def _run_file_job(
        self,
        job_id: JobId,
        prompt_path: Path,
        output_path: Path | None,
        headless: HeadlessFlag,
    ) -> None:
        start_t = time.perf_counter()
        started_at = _utc_now_iso()
        rec = self._storage.get_job(job_id)
        if rec is not None:
            self._storage.save_job(
                JobRecord(
                    job_id=rec.job_id,
                    created_at=rec.created_at,
                    latest_event=rec.latest_event or EVENT_DISPATCH_ACKNOWLEDGED.value,
                    completed=False,
                    started_at=started_at,
                    input_file=rec.input_file,
                    output_file=rec.output_file,
                )
            )

        try:
            res = self._file_only.process_prompt_file_only(
                prompt_file=FilePath(prompt_path),
                output_file=FilePath(output_path) if output_path else None,
                headless=headless,
            )
            duration = round(time.perf_counter() - start_t, 2)
            res_str = str(res) if res is not None else ""
            fail_msg = detect_processing_failure(res_str) or (res_str if res_str.startswith("ERROR") else None)

            if fail_msg:
                self._storage.save_job(
                    JobRecord(
                        job_id=str(job_id),
                        created_at=rec.created_at if rec else started_at,
                        latest_event="EVENT_FAILED",
                        completed=True,
                        started_at=started_at,
                        completed_at=_utc_now_iso(),
                        duration_sec=duration,
                        input_file=str(prompt_path),
                        output_file=str(output_path) if output_path else None,
                        error=fail_msg,
                    )
                )
                return

            preview: str | None = None
            if output_path and output_path.exists():
                try:
                    preview = output_path.read_text(encoding="utf-8")[:500]
                except Exception:
                    preview = res_str[:500] if res_str else None
            elif res_str:
                preview = res_str[:500]

            self._storage.save_job(
                JobRecord(
                    job_id=str(job_id),
                    created_at=rec.created_at if rec else started_at,
                    latest_event=EVENT_GENERATION_FINISHED.value,
                    completed=True,
                    started_at=started_at,
                    completed_at=_utc_now_iso(),
                    duration_sec=duration,
                    input_file=str(prompt_path),
                    output_file=str(output_path) if output_path else None,
                    result_preview=preview,
                )
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_t, 2)
            self._storage.save_job(
                JobRecord(
                    job_id=str(job_id),
                    created_at=rec.created_at if rec else started_at,
                    latest_event="EVENT_FAILED",
                    completed=True,
                    started_at=started_at,
                    completed_at=_utc_now_iso(),
                    duration_sec=duration,
                    input_file=str(prompt_path),
                    output_file=str(output_path) if output_path else None,
                    error=str(exc),
                )
            )

    def _run_attachment_job(
        self,
        job_id: JobId,
        prompt_path: Path,
        attachment_path: Path,
        output_path: Path | None,
        headless: HeadlessFlag,
    ) -> None:
        start_t = time.perf_counter()
        started_at = _utc_now_iso()
        rec = self._storage.get_job(job_id)
        if rec is not None:
            self._storage.save_job(
                JobRecord(
                    job_id=rec.job_id,
                    created_at=rec.created_at,
                    latest_event=rec.latest_event or EVENT_DISPATCH_ACKNOWLEDGED.value,
                    completed=False,
                    started_at=started_at,
                    input_file=rec.input_file,
                    attachment_file=rec.attachment_file,
                    output_file=rec.output_file,
                )
            )

        try:
            res = self._attachment.process_prompt_with_attachment(
                prompt_file=FilePath(prompt_path),
                attachment_file=FilePath(attachment_path),
                output_file=FilePath(output_path) if output_path else None,
                headless=headless,
            )
            duration = round(time.perf_counter() - start_t, 2)
            res_str = str(res) if res is not None else ""
            fail_msg = detect_processing_failure(res_str) or (res_str if res_str.startswith("ERROR") else None)

            if fail_msg:
                self._storage.save_job(
                    JobRecord(
                        job_id=str(job_id),
                        created_at=rec.created_at if rec else started_at,
                        latest_event="EVENT_FAILED",
                        completed=True,
                        started_at=started_at,
                        completed_at=_utc_now_iso(),
                        duration_sec=duration,
                        input_file=str(prompt_path),
                        attachment_file=str(attachment_path),
                        output_file=str(output_path) if output_path else None,
                        error=fail_msg,
                    )
                )
                return

            preview: str | None = None
            if output_path and output_path.exists():
                try:
                    preview = output_path.read_text(encoding="utf-8")[:500]
                except Exception:
                    preview = res_str[:500] if res_str else None
            elif res_str:
                preview = res_str[:500]

            self._storage.save_job(
                JobRecord(
                    job_id=str(job_id),
                    created_at=rec.created_at if rec else started_at,
                    latest_event=EVENT_GENERATION_FINISHED.value,
                    completed=True,
                    started_at=started_at,
                    completed_at=_utc_now_iso(),
                    duration_sec=duration,
                    input_file=str(prompt_path),
                    attachment_file=str(attachment_path),
                    output_file=str(output_path) if output_path else None,
                    result_preview=preview,
                )
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_t, 2)
            self._storage.save_job(
                JobRecord(
                    job_id=str(job_id),
                    created_at=rec.created_at if rec else started_at,
                    latest_event="EVENT_FAILED",
                    completed=True,
                    started_at=started_at,
                    completed_at=_utc_now_iso(),
                    duration_sec=duration,
                    input_file=str(prompt_path),
                    attachment_file=str(attachment_path),
                    output_file=str(output_path) if output_path else None,
                    error=str(exc),
                )
            )

    def get_job_status(self, job_id: JobId | str) -> JobRecord | None:
        """Query status and details of a submitted job."""
        return self._storage.get_job(job_id)

    def list_jobs(self, limit: int = 10) -> list[JobRecord]:
        """List recently submitted jobs."""
        return self._storage.list_jobs(limit)
