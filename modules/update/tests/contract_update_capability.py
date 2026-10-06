"""Contract tests for the update capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.contract_update_aggregate import IUpdateAggregate
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator
from modules.update.src.capabilities_update_manager import UpdateManager

_REQUIRED_PROTOCOL_METHODS: frozenset[str] = frozenset(
    {"current_version", "check_update", "upgrade_package", "sync_browser", "perform_update", "rollback_to"}
)


def test_manager_implements_the_update_protocol() -> None:
    assert IUpdateProtocol in inspect.getmro(UpdateManager)


def test_orchestrator_implements_the_update_aggregate() -> None:
    assert IUpdateAggregate in inspect.getmro(UpdateOrchestrator)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(IUpdateAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_protocol_declares_exactly_the_sealed_method_set() -> None:
    public = {name for name, _ in inspect.getmembers(IUpdateProtocol, predicate=inspect.isfunction)}
    assert public == set(_REQUIRED_PROTOCOL_METHODS)


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for name in _REQUIRED_PROTOCOL_METHODS:
        signature = inspect.signature(getattr(IUpdateProtocol, name))
        assert signature.return_annotation is not inspect.Signature.empty, f"{name} has no return annotation"
