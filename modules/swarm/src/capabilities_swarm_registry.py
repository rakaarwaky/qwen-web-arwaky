"""Capabilities: the shared fan-out state store (AES403).

Implements ISwarmRegistryProtocol.

One file per protocol seam. This file owns ``ISwarmRegistryProtocol`` —
the thread-safe bookkeeping the start, progress, and cancel seams read
and write: the snapshot of every run, the per-role cancel events, the
attachment path, and the executor running the legs.

The three consumer seams live in their own capability files and never
import each other, so this store is what makes them see one fan-out. The
root container creates a single instance and injects it into all three.
It carries bookkeeping only — the retry policy and the status rules stay
in the seam that decides them.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping

from modules.shared.src.common.taxonomy_core_vo import CancelToken, FilePath, TaskExecutor
from modules.shared.src.swarm.contract_swarm_protocol import ISwarmRegistryProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot
from modules.shared.src.swarm.utility_swarm_runner_base import write_manifest

log = logging.getLogger(__name__)


# ─── Block 1: Class Definition & Constructor ────────────
class SwarmRegistry(ISwarmRegistryProtocol):
    """Thread-safe store of every in-flight and finished swarm run.

    One instance per process backs all three seams, so a snapshot read on
    the progress seam and a cancel on the cancel seam always talk about the
    same run. Every write is applied under one lock and persisted to
    ``manifest.json`` before the call returns, so a state change a reader
    observes in memory is also readable on disk.
    """

    def __init__(self) -> None:
        """Start with no runs registered."""
        self._lock = threading.RLock()
        self._snapshots: dict[SwarmId, SwarmSnapshot] = {}
        self._cancel_events: dict[SwarmId, Mapping[str, CancelToken]] = {}
        self._attachments: dict[SwarmId, FilePath] = {}
        self._executors: dict[SwarmId, TaskExecutor] = {}

    # Block 2: Protocol Method Implementation
    def open_run(
        self,
        snapshot: SwarmSnapshot,
        cancel_events: Mapping[str, CancelToken],
        attachment: FilePath,
    ) -> None:
        """Register a new run with its cancel events and attachment, then persist it.

        The snapshot is written before the cancel events are published, so
        a leg that reads its event can already find the run it belongs to.
        """
        with self._lock:
            self._snapshots[snapshot.swarm_id] = snapshot
            self._cancel_events[snapshot.swarm_id] = dict(cancel_events)
            self._attachments[snapshot.swarm_id] = attachment
            write_manifest(snapshot)

    def get_snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when it is unknown."""
        with self._lock:
            return self._snapshots.get(swarm_id)

    def revise(
        self, swarm_id: SwarmId, transform: Callable[[SwarmSnapshot], SwarmSnapshot | None]
    ) -> SwarmSnapshot | None:
        """Replace a stored snapshot with ``transform`` applied, under the registry lock.

        The whole read-decide-write cycle runs under one lock, so two legs
        of the same swarm cannot interleave their status updates and lose
        one another's changes.
        """
        with self._lock:
            current = self._snapshots.get(swarm_id)
            if current is None:
                return None
            updated = transform(current)
            if updated is None:
                return current
            self._snapshots[swarm_id] = updated
            write_manifest(updated)
            return updated

    def cancel_events(self, swarm_id: SwarmId) -> Mapping[str, CancelToken]:
        """Return the per-role cancel events of a swarm, empty when unknown."""
        with self._lock:
            return self._cancel_events.get(swarm_id, {})

    def attachment(self, swarm_id: SwarmId) -> FilePath | None:
        """Return the attachment every leg of a swarm reads, or None when unknown."""
        with self._lock:
            return self._attachments.get(swarm_id)

    def attach_executor(self, swarm_id: SwarmId, executor: TaskExecutor) -> None:
        """Bind the executor that runs the legs of a swarm."""
        with self._lock:
            self._executors[swarm_id] = executor

    def release(self, swarm_id: SwarmId) -> TaskExecutor | None:
        """Drop a swarm's executor, cancel events, and attachment path.

        The snapshot is kept so a caller can still read the terminal state
        of a cancelled run; a leg already in flight sees its event vanish
        and stops reporting instead of launching another browser.
        """
        with self._lock:
            self._cancel_events.pop(swarm_id, None)
            self._attachments.pop(swarm_id, None)
            return self._executors.pop(swarm_id, None)

    # Block 3: Constructors, Std Traits, Helpers
    def __repr__(self) -> str:
        """Report how many runs this registry currently tracks."""
        return f"SwarmRegistry(runs={len(self._snapshots)})"


__all__ = ["SwarmRegistry"]
