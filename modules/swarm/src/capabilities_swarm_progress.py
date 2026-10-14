"""Capabilities: report Swarm progress (AES403).

Implements ISwarmProgressProtocol.

One file per protocol seam. This file owns ``ISwarmProgressProtocol`` —
the single method that returns the latest thread-safe snapshot for a
swarm, or None when the handle is unknown.

The snapshot store this seam reads lives in the shared registry it is
handed, the same registry the start and cancel seams use; no seam imports
another, so the three always report one fan-out.
"""

from __future__ import annotations

import logging

from modules.shared.src.swarm.contract_swarm_protocol import (
    ISwarmProgressProtocol,
    ISwarmRegistryProtocol,
)
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot

log = logging.getLogger(__name__)


# ─── Block 1: Class Definition & Constructor ────────────
class SwarmProgressRunner(ISwarmProgressProtocol):
    """Report the live state of a running fan-out.

    The progress seam owns no state of its own: it reads the snapshot the
    start seam wrote and the leg updates wrote since, so a poller can never
    read a state that is older than the one already persisted to
    ``manifest.json``.
    """

    def __init__(self, registry: ISwarmRegistryProtocol) -> None:
        """Read progress from the shared fan-out registry.

        Args:
            registry: The store the start seam writes every leg update to.
        """
        self._registry = registry

    # Block 2: Protocol Method Implementation
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        return self._registry.get_snapshot(swarm_id)

    # Block 3: Constructors, Std Traits, Helpers


__all__ = ["SwarmProgressRunner"]
