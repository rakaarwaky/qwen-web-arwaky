"""Contract tests for the session capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.session.src.capabilities_session_rotator import SessionRotator
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.contract_session_protocol import (
    ISessionLimitCheckerProtocol,
    ISessionLoginCheckerProtocol,
    ISessionManagerProtocol,
    ISessionRotatorProtocol,
)

_REQUIRED_PROTOCOLS: tuple[type, ...] = (
    ISessionManagerProtocol,
    ISessionLoginCheckerProtocol,
    ISessionLimitCheckerProtocol,
    ISessionRotatorProtocol,
)


def test_rotation_adapter_implements_the_rotator_protocol() -> None:
    assert ISessionRotatorProtocol in inspect.getmro(SessionRotator)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(ISessionAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for protocol in _REQUIRED_PROTOCOLS:
        for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction):
            signature = inspect.signature(getattr(protocol, name))
            assert signature.return_annotation is not inspect.Signature.empty, (
                f"{protocol.__name__}.{name} has no return"
            )


def test_the_rotator_is_async_so_a_health_probe_can_run_per_rotation() -> None:
    assert inspect.iscoroutinefunction(SessionRotator.get_next_session)
