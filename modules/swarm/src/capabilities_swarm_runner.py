"""Capability: start a fan-out over every discovered role template.

One file per protocol seam. This file owns ``ISwarmStartProtocol`` — the
single method that creates a Swarm directory, schedules one browser run
per discovered role template, and returns the initial snapshot.

The fan-out engine state, the lock, and the helpers shared with the
progress and cancel seams live in ``utility_swarm_runner_base``; this file
is a thin class around the start protocol and never carries another
seam's logic.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import FilePath
from modules.shared.src.common.utility_core_prompt_template import list_prompt_templates
from modules.shared.src.swarm.contract_swarm_start import ISwarmStartProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot
from modules.swarm.src.utility_swarm_runner_base import SwarmRunnerBase

log = logging.getLogger(__name__)


class SwarmRunner(SwarmRunnerBase, ISwarmStartProtocol):
    """Run every discovered role template against one attachment.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

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
        swarm_id = self._new_swarm_id()
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
        self._write_manifest(snapshot)
        executor = ThreadPoolExecutor(
            max_workers=self._browser_concurrency,
            thread_name_prefix=f"qwen_swarm_{swarm_id[-6:]}",
        )
        with self._lock:
            self._executors[swarm_id] = executor
            self._replace(snapshot, status="running")
        for role in roles:
            executor.submit(self._run_agent, swarm_id, role)
        return self.snapshot(swarm_id) or snapshot

    def _run_agent(self, swarm_id: SwarmId, role: str) -> None:
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


__all__ = ["SwarmRunner"]