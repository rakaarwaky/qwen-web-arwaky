"""Swarm start capability contract (AES102 `_protocol`).

One file per capability seam. The swarm feature has three seams, and this
file owns the first: starting a fan-out over the discovered role templates
and returning the initial snapshot.

``ISwarmStartProtocol`` carries the single method ``SwarmRunner`` implements
for starting a fan-out, with one concrete return type, so the capability
implements its class outright and never carries stubs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.common.taxonomy_core_vo import FilePath
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmSnapshot

__all__ = ["ISwarmStartProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmStartProtocol": ISwarmStartProtocol,
}


class ISwarmStartProtocol(ABC):
    """Swarm start capability contract."""

    @abstractmethod
    def start(self, input_path: FilePath, attachment_path: FilePath) -> SwarmSnapshot:
        """Start a fan-out over the discovered roles and return the initial snapshot.

        ``input_path`` is what the user pointed at — a file or a folder —
        and is recorded on the snapshot. ``attachment_path`` is the single
        material every role reads; the caller resolves a folder input down
        to it, because the fan-out threads read it on their first pass.
        """
        ...