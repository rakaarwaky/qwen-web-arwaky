"""Contract tests for the logging capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

import pytest

from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.contract_jobs_protocol import IStatusProtocol
from modules.shared.src.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.contract_logging_protocol import IMetricsProtocol, IObservabilityProtocol

_REQUIRED_PROTOCOLS: tuple[type, ...] = (IObservabilityProtocol, IMetricsProtocol)


@pytest.mark.parametrize(
    ("impl", "protocol"),
    [
        (ObservabilitySetup, IObservabilityProtocol),
        (MetricsCounter, IMetricsProtocol),
    ],
    ids=["observability_protocol", "metrics_protocol"],
)
def test_capability_implements_its_protocol(impl: type, protocol: type) -> None:
    assert protocol in inspect.getmro(impl)


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
