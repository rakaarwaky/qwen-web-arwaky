"""Update-domain aggregate contract (AES101 `_aggregate`).

``IUpdateAggregate`` is the single entry point over the update feature.
The CLI update surface calls :meth:`execute`; the agent behind it owns
the rollback decision (run the post-update health gate, then restore the
previous version when the gate fails), so no surface can skip that gate.

The capability seam this aggregate sits on — ``IUpdateProtocol`` — lives
in ``contract_update_protocol.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import UpdateRequest, UpdateResponse


class IUpdateAggregate(ABC):
    """Single entry point over the update feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``UpdateRequest``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: UpdateRequest) -> UpdateResponse:
        """Run the requested update operation and return the result."""
        ...


__all__ = ["IUpdateAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IUpdateAggregate": IUpdateAggregate,
}
