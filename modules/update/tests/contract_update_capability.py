"""Contract tests for the four update FR capability seams."""

from __future__ import annotations

import inspect

from modules.shared.src.update.contract_update_aggregate import IUpdateAggregate
from modules.shared.src.update.contract_update_protocol import (
    IUpdateCheckProtocol,
    IUpdateRollbackProtocol,
    IUpdateUpgradeProtocol,
    IUpdateVerifyProtocol,
)
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator
from modules.update.src.capabilities_update_check import UpdateCheckCapability
from modules.update.src.capabilities_update_rollback import UpdateRollbackCapability
from modules.update.src.capabilities_update_upgrade import UpdateUpgradeCapability
from modules.update.src.capabilities_update_verify import UpdateVerifyCapability

_FR_METHODS: dict[type, frozenset[str]] = {
    IUpdateCheckProtocol: frozenset({"current_version", "check_update"}),
    IUpdateUpgradeProtocol: frozenset({"upgrade_package", "sync_browser"}),
    IUpdateVerifyProtocol: frozenset({"perform_update"}),
    IUpdateRollbackProtocol: frozenset({"rollback_to"}),
}

_FR_CAPABILITIES: dict[type, type] = {
    IUpdateCheckProtocol: UpdateCheckCapability,
    IUpdateUpgradeProtocol: UpdateUpgradeCapability,
    IUpdateVerifyProtocol: UpdateVerifyCapability,
    IUpdateRollbackProtocol: UpdateRollbackCapability,
}


def test_each_fr_protocol_has_a_single_implementing_capability() -> None:
    for proto, capability in _FR_CAPABILITIES.items():
        assert proto in inspect.getmro(capability), f"{capability.__name__} missing {proto.__name__}"


def test_orchestrator_implements_the_update_aggregate() -> None:
    assert IUpdateAggregate in inspect.getmro(UpdateOrchestrator)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(IUpdateAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_each_fr_protocol_seals_its_method_set() -> None:
    for proto, methods in _FR_METHODS.items():
        public = {name for name, _ in inspect.getmembers(proto, predicate=inspect.isfunction)}
        assert public == methods, f"{proto.__name__}: {public} != {methods}"


def test_every_fr_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for proto, methods in _FR_METHODS.items():
        for name in methods:
            signature = inspect.signature(getattr(proto, name))
            assert signature.return_annotation is not inspect.Signature.empty
