"""Capability: report fan-out progress.

One file per protocol seam. This file owns ``ISwarmProgressProtocol`` —
the single method that returns the latest thread-safe snapshot for a
swarm, or None when the handle is unknown.

The fan-out engine state, the lock, and the helpers shared with the
start and cancel seams live in ``utility_swarm_runner_base``; this file is
a thin class around the progress protocol and never carries another
seam's logic.
"""

from __future__ import annotations

import logging

from modules.shared.src.swarm.contract_swarm_progress import ISwarmProgressProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot
from modules.swarm.src.utility_swarm_runner_base import SwarmRunnerBase

log = logging.getLogger(__name__)


class SwarmRunner(SwarmRunnerBase, ISwarmProgressProtocol):
    """Run every discovered role template against one attachment.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        with self._lock:
            return self._snapshots.get(swarm_id)


__all__ = ["SwarmRunner"]