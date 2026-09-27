"""Swarm-domain capability contract (AES102 `_protocol`).

One file for the swarm feature. The swarm feature has one capability
seam, ``ISwarmProtocol``: it carries every method ``SwarmRunner``
implements, with one concrete return type each, so the capability
implements its class outright and never carries stubs.

``ISwarmAggregate`` in ``contract_swarm_aggregate.py`` is the outward
export surface for outer layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import FilePath
from modules.shared.src.taxonomy_swarm_vo import BrowserCount, SwarmId, SwarmSnapshot


class ISwarmProtocol(ABC):
    """Swarm execution and tracking capability contract."""

    @property
    @abstractmethod
    def browser_concurrency(self) -> BrowserCount:
        """Return how many browsers a single Swarm run may launch at once."""
        ...

    @abstractmethod
    def start(self, input_path: FilePath, attachment_path: FilePath) -> SwarmSnapshot:
        """Start a fan-out over the discovered roles and return the initial snapshot.

        ``input_path`` is what the user pointed at — a file or a folder —
        and is recorded on the snapshot. ``attachment_path`` is the single
        material every role reads; the caller resolves a folder input down
        to it, because the fan-out threads read it on their first pass.
        """
        ...

    @abstractmethod
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        ...

    @abstractmethod
    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a swarm."""
        ...


__all__ = ["ISwarmProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmProtocol": ISwarmProtocol,
}
