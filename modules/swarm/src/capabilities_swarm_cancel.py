"""Capabilities: cancel a running fan-out (AES403).

Implements ISwarmCancelProtocol.

One file per protocol seam. This file owns ``ISwarmCancelProtocol`` —
the single method that stops every leg of a running fan-out, marks the
survivors cancelled, and shuts the executor down.

The fan-out engine state, the lock, and the helpers shared with the
start and progress seams live in ``capabilities_swarm_runner``; this file
is a thin class around the cancel protocol and never carries another
seam's logic.
"""

from __future__ import annotations

import logging

from modules.shared.src.swarm.contract_swarm_protocol import ISwarmCancelProtocol
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

log = logging.getLogger(__name__)

# ─── Block 1: Class Definition & Constructor ────────────
class SwarmCancelRunner(SwarmRunner, ISwarmCancelProtocol):
    """Cancel a running fan-out on behalf of the swarm orchestrator.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

    # Block 2: Protocol Method Implementation
    def cancel(self, swarm_id: SwarmId) -> None:
        """Stop active browser contexts and prevent queued work from running."""
        super().cancel(swarm_id)

    # Block 3: Constructors, Std Traits, Helpers


__all__ = ["SwarmCancelRunner"]