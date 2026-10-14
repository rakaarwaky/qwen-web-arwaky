"""Swarm progress capability contract (AES102 `_protocol`).

One file per capability seam. The swarm feature has three seams, and this
file owns the second: reporting the current state of a running fan-out.

``ISwarmProgressProtocol`` carries the single method ``SwarmRunner``
implements for polling a fan-out, with one concrete return type, so the
capability implements its class outright and never carries stubs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId, SwarmSnapshot

__all__ = ["ISwarmProgressProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmProgressProtocol": "ISwarmProgressProtocol",
}


class ISwarmProgressProtocol(ABC):
    """Swarm progress capability contract."""

    @abstractmethod
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        ...