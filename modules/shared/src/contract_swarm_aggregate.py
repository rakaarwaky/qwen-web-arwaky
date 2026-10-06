"""Swarm-domain aggregate contract (AES101 `_aggregate`).

``ISwarmAggregate`` is the single entry point over the swarm feature.
The TUI, CLI, and MCP surfaces call :meth:`execute`; the agent behind
the aggregate owns the routing from a ``SwarmRequest`` verb to the
swarm runner, so no surface can skip the admission or resource-governance
guards that every Swarm fan-out depends on.

Operation-specific verbs live in the ``SwarmRequest.verb`` field; all
consumer arguments ride on ``SwarmRequest``, and the result shape is a
single ``SwarmResponse``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_swarm_vo import SwarmRequest, SwarmResponse


class ISwarmAggregate(ABC):
    """Single entry point over the swarm feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``SwarmRequest.verb``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: SwarmRequest) -> SwarmResponse:
        """Run one swarm operation and return the result.

        Routes *request* to the matching runner operation and returns a
        single response VO. For ``start``, the initial ``SwarmSnapshot``
        is returned as ``response.snapshot``; for ``snapshot``, the
        latest state; for ``cancel``, the post-cancel state. A missing
        argument is reported as ``response.error``.
        """
        ...


__all__ = ["ISwarmAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmAggregate": ISwarmAggregate,
}
