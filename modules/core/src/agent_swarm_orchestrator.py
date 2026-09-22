"""Agent orchestration for the Swarm MVP."""

from __future__ import annotations

import json
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from modules.shared.src.contract_core_aggregate import IAttachmentPromptAggregate
from modules.shared.src.contract_core_protocol import IFolderToAttachmentProtocol
from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS, MAX_ATTEMPTS, SWARM_OUTPUT_ROOT
from modules.shared.src.taxonomy_core_vo import HeadlessFlag
from modules.shared.src.taxonomy_swarm_vo import AgentStatus, SwarmAgentSnapshot, SwarmId, SwarmSnapshot, SwarmStatus
from modules.shared.src.utility_core_prompt_template import list_prompt_templates, materialize_role_template
from modules.shared.src.utility_core_response import detect_processing_failure


class SwarmOrchestrator(ISwarmAggregate):
    """Run every discovered role template against one attachment."""

    def __init__(
        self,
        attachment: IAttachmentPromptAggregate,
        folder_adapter: IFolderToAttachmentProtocol | None = None,
        output_root: Path = SWARM_OUTPUT_ROOT,
        browser_concurrency: int = DEFAULT_MAX_WORKERS,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._attachment = attachment
        self._folder_adapter = folder_adapter
        self._output_root = Path(output_root)
        self._browser_concurrency = min(10, max(1, int(browser_concurrency)))
        self._max_attempts = max(1, int(max_attempts))
        self._lock = threading.RLock()
        self._snapshots: dict[SwarmId, SwarmSnapshot] = {}
        self._cancel_events: dict[SwarmId, dict[str, threading.Event]] = {}
        self._executors: dict[SwarmId, ThreadPoolExecutor] = {}
        self._attachment_paths: dict[SwarmId, Path] = {}

    def start(self, input_path: Path) -> SwarmSnapshot:
        """Create a Swarm directory and schedule all discovered templates."""
        source = Path(input_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Swarm input does not exist: {source}")
        roles = list_prompt_templates()
        if not roles:
            raise RuntimeError("No prompt templates were discovered")
        swarm_id = self._new_swarm_id()
        root = self._output_root / swarm_id
        root.mkdir(parents=True, exist_ok=False)
        attachment_path = source
        if source.is_dir() and self._folder_adapter is not None:
            attachment_path = self._folder_adapter.resolve_to_attachment(source)
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
            self._attachment_paths[swarm_id] = attachment_path
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

    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return a thread-safe immutable snapshot."""
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
            cancelled = SwarmSnapshot(
                swarm_id=snapshot.swarm_id,
                input_path=snapshot.input_path,
                root_path=snapshot.root_path,
                status="cancelled",
                max_attempts=snapshot.max_attempts,
                browser_concurrency=snapshot.browser_concurrency,
                agents=updated,
            )
            self._snapshots[swarm_id] = cancelled
            self._write_manifest(cancelled)
            executor = self._executors.pop(swarm_id, None)
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
            self._cancel_events.pop(swarm_id, None)
            self._attachment_paths.pop(swarm_id, None)

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
            self._update_agent(
                swarm_id, role, "running" if attempt == 1 else "retrying", attempt, output_path, None, start
            )
            try:
                prompt_file = materialize_role_template(role)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result = self._attachment.process_prompt_with_attachment(
                    prompt_file=prompt_file,
                    attachment_file=attachment_path,
                    output_file=output_path,
                    headless=HeadlessFlag(True),
                    cancel_event=event,
                )
                result_text = str(result)
                if detect_processing_failure(result_text):
                    last_error = result_text
                    if not self._is_retryable(last_error) or attempt == self._max_attempts:
                        self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                        return
                    continue
                self._update_agent(swarm_id, role, "completed", attempt, output_path, None, start)
                return
            except Exception as exc:
                last_error = str(exc)
                if event.is_set():
                    self._update_agent(swarm_id, role, "cancelled", attempt, output_path, "Cancelled by user", start)
                    return
                if not self._is_retryable(last_error) or attempt == self._max_attempts:
                    self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                    return
        self._update_agent(swarm_id, role, "failed", self._max_attempts, output_path, last_error, start)

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
        with self._lock:
            snapshot = self._snapshots.get(swarm_id)
            if snapshot is None:
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
                for agent in snapshot.agents
            )
            if snapshot.status == "cancelled":
                return
            finished = all(agent.status in {"completed", "failed", "cancelled"} for agent in agents)
            final_status = snapshot.status
            if finished:
                final_status = "completed" if all(agent.status == "completed" for agent in agents) else "partial"
            updated = SwarmSnapshot(
                swarm_id=snapshot.swarm_id,
                input_path=snapshot.input_path,
                root_path=snapshot.root_path,
                status=final_status,
                max_attempts=snapshot.max_attempts,
                browser_concurrency=snapshot.browser_concurrency,
                agents=agents,
            )
            self._snapshots[swarm_id] = updated
            self._write_manifest(updated)
            if finished:
                executor = self._executors.pop(swarm_id, None)
                self._cancel_events.pop(swarm_id, None)
                self._attachment_paths.pop(swarm_id, None)
                if executor is not None:
                    executor.shutdown(wait=False, cancel_futures=False)

    def _replace(self, snapshot: SwarmSnapshot, status: SwarmStatus) -> None:
        updated = SwarmSnapshot(
            swarm_id=snapshot.swarm_id,
            input_path=snapshot.input_path,
            root_path=snapshot.root_path,
            status=status,
            max_attempts=snapshot.max_attempts,
            browser_concurrency=snapshot.browser_concurrency,
            agents=snapshot.agents,
        )
        self._snapshots[snapshot.swarm_id] = updated
        self._write_manifest(updated)

    def _write_manifest(self, snapshot: SwarmSnapshot) -> None:
        data = {
            "swarm_id": snapshot.swarm_id,
            "status": snapshot.status,
            "input_path": str(snapshot.input_path),
            "agent_count": len(snapshot.agents),
            "completed": snapshot.completed_count,
            "failed": snapshot.failed_count,
            "max_attempts": snapshot.max_attempts,
            "browser_concurrency": snapshot.browser_concurrency,
            "agents": [
                {
                    "id": agent.agent_id,
                    "status": agent.status,
                    "attempt": agent.attempt,
                    "output_path": str(agent.output_path.relative_to(snapshot.root_path))
                    if agent.output_path
                    else None,
                    "error": agent.error,
                    "duration_sec": agent.duration_sec,
                }
                for agent in snapshot.agents
            ],
        }
        target = snapshot.root_path / "manifest.json"
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _request_attachment_cancel(self, event: threading.Event) -> None:
        # ``request_cancel`` is part of IAttachmentPromptAggregate (cancel is a
        # first-class contract operation), so a direct typed call replaces the
        # former getattr() duck-typing hack.
        self._attachment.request_cancel(event)

    @staticmethod
    def _is_retryable(message: str) -> bool:
        lowered = message.lower()
        return any(
            token in lowered
            for token in ("rate", "429", "timeout", "timed out", "connection", "network", "empty", "stuck")
        )

    @staticmethod
    def _new_swarm_id() -> SwarmId:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return SwarmId(f"swarm_{timestamp}_{secrets.token_hex(3)}")


__all__ = ["SwarmOrchestrator"]
