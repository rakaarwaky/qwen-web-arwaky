"""Swarm-domain capability contract (AES102 `_protocol`).

One file for the swarm feature, carrying one class per capability seam.
The swarm feature has three seams — start, progress, cancel — each sealed
in its own protocol class so a concrete runner implements all three and a
test can inject a stub that only implements the seam it is exercising.

A single protocol file may declare many protocol classes: the count the
linter compares against the FR count is the class count, never the file
count. Three classes here match the three FR-SWARM requirements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.common.taxonomy_core_vo import FilePath
from modules.shared.src.swarm.taxonomy_swarm_vo import BrowserCount, SwarmId, SwarmSnapshot

__all__ = [
    "ISwarmStartProtocol",
    "ISwarmProgressProtocol",
    "ISwarmCancelProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmStartProtocol": "ISwarmStartProtocol",
    "ISwarmProgressProtocol": "ISwarmProgressProtocol",
    "ISwarmCancelProtocol": "ISwarmCancelProtocol",
}


class ISwarmStartProtocol(ABC):
    """Swarm start capability contract."""

    @property
    @abstractmethod
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
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


class ISwarmProgressProtocol(ABC):
    """Swarm progress capability contract."""

    @abstractmethod
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        ...


class ISwarmCancelProtocol(ABC):
    """Swarm cancel capability contract."""

    @abstractmethod
    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a swarm."""
        ...
