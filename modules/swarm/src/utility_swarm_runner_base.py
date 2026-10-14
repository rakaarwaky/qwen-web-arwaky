"""Utility layer (utility_swarm_runner_base): shared fan-out engine state.

The swarm runner owns one fan-out engine but exposes three capability
seams — start, progress, cancel — each sealed in its own protocol file.
This utility holds the state, the lock, and the helpers that every seam
needs, so each capability file stays a thin class around one protocol and
never carries another seam's logic.

It is not a protocol: it is stateless wiring the capability files import.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
from modules.shared.src.swarm.taxonomy_swarm_vo import (
    AgentStatus,
    BrowserCount,
    SwarmAgentSnapshot,
    SwarmId,
    SwarmSnapshot,
    SwarmStatus,
)

log = logging.getLogger(__name__)


class SwarmRunnerBase:
    """Shared fan-out engine state and helpers for the swarm capability files.

    Subclasses implement one protocol seam each. The base owns the
    thread-safe snapshot store, the cancellation events, the executors,
    and the helpers that every seam reads — so a seam file never re-states
    another seam's logic.
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
        # Host capacity is the ceiling for a fan-out: an explicit request above
        # it is clamped so a Swarm cannot OOM the runner (issue #291).
        self._browser_concurrency = min(recommended_max_workers(), max(1, concurrency))
        self._max_attempts = max(1, int(max_attempts))
        self._circuit_breaker = circuit_breaker
        self._rate_limiter = rate_limiter
        self._lock = threading.RLock()
        self._snapshots: dict[SwarmId, SwarmSnapshot] = {}
        self._cancel_events: dict[SwarmId, dict[str, threading.Event]] = {}
        self._executors: dict[SwarmId, ThreadPoolExecutor] = {}
        self._attachment_paths: dict[SwarmId, Path] = {}

    @property
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
        return BrowserCount(self._browser_concurrency)

    def _new_swarm_id(self) -> SwarmId:
        """Generate a short, URL-safe swarm identifier."""
        return SwarmId(f"swarm-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}")

    def _write_manifest(self, snapshot: SwarmSnapshot) -> None:
        """Persist the snapshot as JSON next to the swarm output root."""
        manifest = snapshot.root_path / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "swarm_id": snapshot.swarm_id,
                    "input_path": str(snapshot.input_path),
                    "root_path": str(snapshot.root_path),
                    "status": snapshot.status,
                    "max_attempts": snapshot.max_attempts,
                    "browser_concurrency": snapshot.browser_concurrency,
                    "agents": [
                        {
                            "agent_id": agent.agent_id,
                            "status": agent.status,
                            "attempt": agent.attempt,
                            "output_path": str(agent.output_path),
                            "error": agent.error,
                            "duration_sec": agent.duration_sec,
                        }
                        for agent in snapshot.agents
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _replace(self, snapshot: SwarmSnapshot, status: SwarmStatus) -> None:
        """Return a copy of *snapshot* with its status replaced."""
        with self._lock:
            current = self._snapshots.get(snapshot.swarm_id)
            if current is None:
                return
            updated = SwarmSnapshot(
                swarm_id=current.swarm_id,
                input_path=current.input_path,
                root_path=current.root_path,
                status=status,
                max_attempts=current.max_attempts,
                browser_concurrency=current.browser_concurrency,
                agents=current.agents,
            )
            self._snapshots[snapshot.swarm_id] = updated
            self._write_manifest(updated)

    def _request_attachment_cancel(self, event: threading.Event) -> None:
        """Forward a cancel event to the attachment aggregate, if it accepts one."""
        request_cancel = getattr(self._attachment, "request_cancel", None)
        if callable(request_cancel):
            request_cancel(event)

    @staticmethod
    def _is_retryable(message: str) -> bool:
        """Return True when *message* names a transient failure worth retrying."""
        lowered = message.casefold()
        return any(token in lowered for token in ("timeout", "transient", "rate limit", "503", "502", "504", "temporarily"))

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
                    if not self._is_retryable(last_error) or attempt == self._max_attempts:
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
                if not self._is_retryable(last_error) or attempt == self._max_attempts:
                    self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                    return
        self._update_agent(swarm_id, role, "failed", self._max_attempts, output_path, last_error, start)


__all__ = ["SwarmRunnerBase"]