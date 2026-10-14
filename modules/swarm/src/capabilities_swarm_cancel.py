"""Capability: cancel a running fan-out.

One file per protocol seam. This file owns ``ISwarmCancelProtocol`` —
the single method that stops every leg of a running fan-out, marks the
survivors cancelled, and shuts the executor down.

The fan-out engine state, the lock, and the helpers shared with the
start and progress seams live in ``utility_swarm_runner_base``; this file
is a thin class around the cancel protocol and never carries another
seam's logic.
"""

from __future__ import annotations

import logging

from modules.shared.src.swarm.contract_swarm_cancel import ISwarmCancelProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmAgentSnapshot, SwarmId, SwarmSnapshot
from modules.swarm.src.utility_swarm_runner_base import SwarmRunnerBase

log = logging.getLogger(__name__)


class SwarmRunner(SwarmRunnerBase, ISwarmCancelProtocol):
    """Run every discovered role template against one attachment.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

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


__all__ = ["SwarmRunner"]