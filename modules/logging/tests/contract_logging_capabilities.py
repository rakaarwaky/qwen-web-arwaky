"""Contract tests for the logging capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.contract_core_protocol import IMetricsProtocol, IStatusProtocol
from modules.shared.src.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol

_REQUIRED_PROTOCOLS: tuple[type, ...] = (IObservabilityProtocol, IMetricsProtocol)


def test_observability_implements_the_observability_protocol() -> None:
    assert IObservabilityProtocol in inspect.getmro(ObservabilitySetup)


def test_metrics_counter_implements_the_metrics_protocol() -> None:
    assert IMetricsProtocol in inspect.getmro(MetricsCounter)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(IObservabilityAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for protocol in (*_REQUIRED_PROTOCOLS, IStatusProtocol):
        for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction):
            signature = inspect.signature(getattr(protocol, name))
            assert signature.return_annotation is not inspect.Signature.empty, (
                f"{protocol.__name__}.{name} has no return"
            )
