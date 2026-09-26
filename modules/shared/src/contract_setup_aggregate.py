"""Setup aggregate contract (AES101 `_aggregate`).

``ISetupAggregate`` is the single entry point over the interactive
manual-login feature. The CLI and interactive controller call
``execute``; the agent behind it owns the launch → navigate → CAPTCHA
→ validate sequence, so no surface can forget the authentication check
every manual-login run depends on.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import SetupRequest, SetupResponse


class ISetupAggregate(ABC):
    """Single entry point over the setup feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``SetupRequest``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: SetupRequest) -> SetupResponse:
        """Run the requested setup operation and return the result."""
        ...


__all__ = ["ISetupAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {"ISetupAggregate": ISetupAggregate}
