"""Swarm aggregate contract for the CLI surface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from modules.shared.src.taxonomy_swarm_vo import SwarmId, SwarmSnapshot


class ISwarmAggregate(ABC):
    """Public Swarm workflow operations."""

    @abstractmethod
    def start(self, input_path: Path) -> SwarmSnapshot:
        """Start a Swarm and return its initial snapshot."""

    @abstractmethod
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a Swarm."""

    @abstractmethod
    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a Swarm."""


__all__ = ["ISwarmAggregate"]
