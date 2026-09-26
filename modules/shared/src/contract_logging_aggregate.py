"""Logging-domain aggregate contract (AES101 `_aggregate`).

``IObservabilityAggregate`` is the single entry point over the logging
feature. The root container and the CLI surfaces call :meth:`execute`;
the agent behind it owns the observability bootstrap, the status file,
and the quality report, so no surface can skip the scrubber that keeps
session tokens out of telemetry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import (
    ObservabilityRequest,
    ObservabilityResponse,
)


class IObservabilityAggregate(ABC):
    """Single entry point over the logging feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``ObservabilityRequest``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: ObservabilityRequest) -> ObservabilityResponse:
        """Run the requested observability operation and return the result."""
        ...


__all__ = ["IObservabilityAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IObservabilityAggregate": IObservabilityAggregate,
}
