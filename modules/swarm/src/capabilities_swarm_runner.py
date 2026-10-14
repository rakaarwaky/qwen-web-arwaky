"""Capabilities: the swarm fan-out engine (AES403).

Implements ISwarmStartProtocol, ISwarmProgressProtocol, ISwarmCancelProtocol.

One file owns the fan-out engine — the thread-safe snapshot store, the
cancellation events, the executors, and the per-role retry loop — while
three protocol seams (start, progress, cancel) describe what a caller may
do. The stateless helpers (retry predicate, snapshot-status replacement,
manifest writer) live in ``utility_swarm_runner_base`` so this file is a
thin class around the engine and never re-states another seam's logic.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import MAX_ATTEMPTS, SWARM_OUTPUT_ROOT
from modules.shared.src.common.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.common.taxonomy_core_vo import FilePath, HeadlessFlag
from modules.shared.src.common.utility_core_capacity import recommended_max_workers
from modules.shared.src.common.utility_core_prompt_template import (
    list_prompt_templates,
    materialize_role_template,
)
from modules.shared.src.common.utility_response_normalizer import detect_processing_failure
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse
from modules.shared.src.swarm.contract_swarm_protocol import (
    ISwarmCancelProtocol,
    ISwarmProgressProtocol,
    ISwarmStartProtocol,
)
from modules.shared.src.swarm.taxonomy_swarm_vo import (
    AgentStatus,
    BrowserCount,
    SwarmAgentSnapshot,
    SwarmId,
    SwarmSnapshot,
    SwarmStatus,
)
from modules.swarm.src.utility_swarm_runner_base import (
    is_retryable,
    new_swarm_id,
    replace_status,
    write_manifest,
)

log = logging.getLogger(__name__)


# ─── Block 1: Class Definition & Constructor ────────────
class SwarmRunner(ISwarmStartProtocol, ISwarmProgressProtocol, ISwarmCancelProtocol):
    """Run every discovered role template against one attachment.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

    def __init__(
        self,
        attachment: IPromptAggregate,
        output_root: Path = SWARM_OUTPUT_ROOT,
        browser_concurrency: int | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        headless: bool = True,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Wire the fan-out engine to the attachment aggregate it fans out over.

        ``attachment`` is the single material every role reads. The host
        capacity is the ceiling for a fan-out: an explicit request above
        it is clamped so a Swarm cannot OOM the runner (issue #291).
        """
        self._attachment = attachment
        self._output_root = Path(output_root)
        self._headless = bool(headless)
        if browser_concurrency is None:
            swarm_env = os.environ.get("QWA_SWARM_CONCURRENCY", "").strip()
            concurrency = (
                int(swarm_env)
                if swarm_env.isdigit() and int(swarm_env) > 0
                else recommended_max_workers()
            )
        else:
            concurrency = int(browser_concurrency)
        self._browser_concurrency = min(recommended_max_workers(), max(1, concurrency))
        self._max_attempts = max(1, int(max_attempts))
        self._circuit_breaker = circuit_breaker
        self._rate_limiter = rate_limiter
        self._lock = threading.RLock()
        self._snapshots: dict[SwarmId, SwarmSnapshot] = {}
        self._cancel_events: dict[SwarmId, dict[str, threading.Event]] = {}
        self._executors: dict[SwarmId, ThreadPoolExecutor] = {}
        self._attachment_paths: dict[SwarmId, Path] = {}

    # Block 2: Protocol Method Implementation
    @property
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
        return BrowserCount(self._browser_concurrency)

    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        with self._lock:
            return self._snapshots.get(swarm_id)

    def cancel(self, swarm_id: SwarmId) -> None:
        """Stop active browser contexts and prevent queued work from running."""
        with self._lock:
            snapshot = self._snapshots.get(swarm_id)
            events = self._cancel_events.get(swarm_id, {})
            if snapshot is None:
                return
            for event in events.values():
                event.set()
            for event in events.values():
                self._request_attachment_cancel(event)
            updated = tuple(
                agent
                if agent.status in {"completed", "failed"}
                else SwarmAgentSnapshot(
                    agent_id=agent.agent_id,
                    status="cancelled",
                    attempt=agent.attempt,
                    output_path=agent.output_path,
                    error="Cancelled by user",
                    duration_sec=agent.duration_sec,
                )
                for agent in snapshot.agents
            )
            self._snapshots[swarm_id] = replace_status(
                SwarmSnapshot(
                    swarm_id=snapshot.swarm_id,
                    input_path=snapshot.input_path,
                    root_path=snapshot.root_path,
                    status="cancelled",
                    max_attempts=snapshot.max_attempts,
                    browser_concurrency=snapshot.browser_concurrency,
                    agents=updated,
                ),
                "cancelled",
            )
            write_manifest(self._snapshots[swarm_id])
            executor = self._executors.pop(swarm_id, None)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def start(self, input_path: FilePath, attachment_path: FilePath) -> SwarmSnapshot:
        """Create a Swarm directory and schedule all discovered templates.

        ``input_path`` is what the user pointed at and is recorded on the
        snapshot; ``attachment_path`` is the single material every role
        reads. The caller resolves a folder input down to one attachment
        before calling, because the agent threads below are submitted
        immediately and read this path on their first pass.
        """
        source = Path(input_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Swarm input does not exist: {source}")
        roles = list_prompt_templates()
        if not roles:
            raise RuntimeError("No prompt templates were discovered")
        swarm_id = new_swarm_id()
        root = self._output_root / swarm_id
        root.mkdir(parents=True, exist_ok=False)
        agents = tuple(
            SwarmAgentSnapshot(agent_id=role, status="queued", output_path=root / role / "output.md") for role in roles
        )
        snapshot = SwarmSnapshot(
            swarm_id=swarm_id,
            input_path=source,
            root_path=root,
            status="queued",
            max_attempts=self._max_attempts,
            browser_concurrency=self._browser_concurrency,
            agents=agents,
        )
        with self._lock:
            self._snapshots[swarm_id] = snapshot
            self._cancel_events[swarm_id] = {role: threading.Event() for role in roles}
            self._attachment_paths[swarm_id] = Path(attachment_path)
        write_manifest(snapshot)
        executor = ThreadPoolExecutor(
            max_workers=self._browser_concurrency,
            thread_name_prefix=f"qwen_swarm_{swarm_id[-6:]}",
        )
        with self._lock:
            self._executors[swarm_id] = executor
            self._snapshots[swarm_id] = replace_status(snapshot, "running")
        for role in roles:
            executor.submit(self._run_agent, swarm_id, role)
        return self.snapshot(swarm_id) or snapshot

    # Block 3: Constructors, Std Traits, Helpers
    def _update_agent(
        self,
        swarm_id: SwarmId,
        role: str,
        status: AgentStatus,
        attempt: int,
        output_path: Path,
        error: str | None,
        started: float,
    ) -> None:
        """Update one agent's status in the snapshot and persist the manifest."""
        with self._lock:
            current = self._snapshots.get(swarm_id)
            if current is None:
                return
            agents = tuple(
                SwarmAgentSnapshot(
                    agent_id=agent.agent_id,
                    status=status if agent.agent_id == role else agent.status,
                    attempt=attempt if agent.agent_id == role else agent.attempt,
                    output_path=output_path if agent.agent_id == role else agent.output_path,
                    error=error if agent.agent_id == role else agent.error,
                    duration_sec=round(time.perf_counter() - started, 2)
                    if agent.agent_id == role
                    else agent.duration_sec,
                )
                for agent in current.agents
            )
            if current.status == "cancelled":
                return
            finished = all(agent.status in {"completed", "failed", "cancelled"} for agent in agents)
            final_status: SwarmStatus = current.status
            if finished:
                final_status = "completed" if all(agent.status == "completed" for agent in agents) else "partial"
            updated = SwarmSnapshot(
                swarm_id=current.swarm_id,
                input_path=current.input_path,
                root_path=current.root_path,
                status=final_status,
                max_attempts=current.max_attempts,
                browser_concurrency=current.browser_concurrency,
                agents=agents,
            )
            self._snapshots[swarm_id] = updated
            write_manifest(updated)

    def _request_attachment_cancel(self, event: threading.Event) -> None:
        """Forward a cancel event to the attachment aggregate via its typed seam.

        ``IPromptAggregate.request_cancel`` is a first-class contract
        operation, so the Swarm runner reaches it through ``execute`` with
        the ``request_cancel`` verb rather than duck-typing on an attribute
        that may or may not exist (issue #360).
        """
        self._attachment.execute(
            PromptRequest(verb="request_cancel", cancel_event=event)
        )

    def _run_agent(self, swarm_id: SwarmId, role: str) -> None:
        """Execute one fan-out leg with retries, bounded by the cancel event.

        The start seam schedules this per role; the loop itself is engine
        mechanics shared conceptually with the whole fan-out, so it lives
        in the base rather than in any one capability file.
        """
        start = time.perf_counter()
        with self._lock:
            events_map = self._cancel_events.get(swarm_id, {})
            event = events_map.get(role)
            attachment_path = self._attachment_paths.get(swarm_id)
        output_path = self._output_root / swarm_id / role / "output.md"
        last_error = "Unknown Swarm agent failure"
        if event is None or attachment_path is None:
            self._update_agent(swarm_id, role, "cancelled", 0, output_path, "Cancelled by user", start)
            return
        for attempt in range(1, self._max_attempts + 1):
            if event.is_set():
                self._update_agent(swarm_id, role, "cancelled", attempt - 1, output_path, "Cancelled by user", start)
                return
            if self._circuit_breaker is not None and self._circuit_breaker.is_tripped:
                # The breaker only gates the agent in front of it: siblings keep
                # their in-flight browsers, so the swarm ends partial, not aborted.
                self._update_agent(
                    swarm_id,
                    role,
                    "failed",
                    attempt - 1,
                    output_path,
                    "Swarm paused: too many recent failures tripped the circuit breaker",
                    start,
                )
                return
            if self._rate_limiter is not None:
                wait_sec = self._rate_limiter.try_acquire()
                if wait_sec is not None:
                    self._update_agent(
                        swarm_id, role, "running" if attempt == 1 else "retrying", attempt, output_path, None, start
                    )
                    if event.wait(wait_sec):
                        self._update_agent(
                            swarm_id, role, "cancelled", attempt - 1, output_path, "Cancelled by user", start
                        )
                        return
            self._update_agent(
                swarm_id, role, "running" if attempt == 1 else "retrying", attempt, output_path, None, start
            )
            try:
                prompt_file = materialize_role_template(role)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                resp: PromptResponse = self._attachment.execute(
                    PromptRequest(
                        verb="process_prompt_with_attachment",
                        prompt_file=prompt_file,
                        attachment_file=attachment_path,
                        output_file=output_path,
                        headless=HeadlessFlag(self._headless),
                        cancel_event=event,
                    )
                )
                result_text = resp.response_text or ""
                if detect_processing_failure(result_text):
                    last_error = result_text
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_failure()
                    if not is_retryable(last_error) or attempt == self._max_attempts:
                        self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                        return
                    continue
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_success()
                self._update_agent(swarm_id, role, "completed", attempt, output_path, None, start)
                return
            except Exception as exc:
                last_error = str(exc)
                if event.is_set():
                    self._update_agent(swarm_id, role, "cancelled", attempt, output_path, "Cancelled by user", start)
                    return
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_failure()
                if not is_retryable(last_error) or attempt == self._max_attempts:
                    self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                    return
        self._update_agent(swarm_id, role, "failed", self._max_attempts, output_path, last_error, start)


__all__ = ["SwarmRunner"]