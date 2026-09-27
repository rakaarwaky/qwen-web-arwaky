"""Session-domain aggregate contract (AES101 `_aggregate`).

The single entry point over the session feature: the consumer (surface,
root, CLI, MCP) calls :meth:`execute` with a :class:`SessionRequest`;
the agent behind the aggregate dispatches to the capability seams in
``contract_session_protocol.py``.

Adding a consumer verb means adding a variant to ``SessionRequest``,
never a second aggregate method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_session_vo import SessionRequest, SessionResponse


class ISessionAggregate(ABC):
    """Single entry point over the session feature.

    Exactly one method: the door consumers knock on.
    """

    @abstractmethod
    def execute(self, request: SessionRequest) -> SessionResponse:
        """Run the requested session verb and return its outcome."""
        ...


__all__ = ["ISessionAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISessionAggregate": ISessionAggregate,
}
