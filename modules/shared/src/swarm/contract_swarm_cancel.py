"""Swarm cancel capability contract (AES102 `_protocol`).

One file per capability seam. The swarm feature has three seams, and this
file owns the third: stopping every leg of a running fan-out.

``ISwarmCancelProtocol`` carries the single method ``SwarmRunner``
implements for cancelling a fan-out, with one concrete return type, so the
capability implements its class outright and never carries stubs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId

__all__ = ["ISwarmCancelProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmCancelProtocol": ISwarmCancelProtocol,
}


class ISwarmCancelProtocol(ABC):
    """Swarm cancel capability contract."""

    @abstractmethod
    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a swarm."""
        ...