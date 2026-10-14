"""Capabilities: report fan-out progress (AES403).

Implements ISwarmProgressProtocol.

One file per protocol seam. This file owns ``ISwarmProgressProtocol`` —
the single method that returns the latest thread-safe snapshot for a
swarm, or None when the handle is unknown.

The fan-out engine state, the lock, and the helpers shared with the
start and cancel seams live in ``capabilities_swarm_runner``; this file
is a thin class around the progress protocol and never carries another
seam's logic.
"""

from __future__ import annotations

import logging

from modules.shared.src.swarm.contract_swarm_protocol import ISwarmProgressProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

log = logging.getLogger(__name__)

# ─── Block 1: Class Definition & Constructor ────────────
class SwarmProgressRunner(SwarmRunner, ISwarmProgressProtocol):
    """Report fan-out progress on behalf of the swarm orchestrator.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

    # Block 2: Protocol Method Implementation
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        return super().snapshot(swarm_id)

    # Block 3: Constructors, Std Traits, Helpers


__all__ = ["SwarmProgressRunner"]