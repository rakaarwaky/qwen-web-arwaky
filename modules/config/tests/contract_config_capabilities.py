"""Contract tests for the config capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.config.src.agent_config_orchestrator import ConfigOrchestrator
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.contract_config_aggregate import IConfigAggregate
from modules.shared.src.contract_config_protocol import (
    IConfigPathResolverProtocol,
    IConfigSlotPlanProtocol,
    IConfigValidatorProtocol,
)

_REQUIRED_PROTOCOLS: tuple[type, ...] = (
    IConfigValidatorProtocol,
    IConfigPathResolverProtocol,
    IConfigSlotPlanProtocol,
)


def test_orchestrator_implements_the_config_aggregate() -> None:
    assert IConfigAggregate in inspect.getmro(ConfigOrchestrator)


def test_validator_implements_the_validator_protocol() -> None:
    assert IConfigValidatorProtocol in inspect.getmro(ConfigValidator)


def test_path_resolver_implements_the_path_resolver_protocol() -> None:
    assert IConfigPathResolverProtocol in inspect.getmro(ConfigPathResolver)


def test_slot_resolver_implements_the_slot_plan_protocol() -> None:
    assert IConfigSlotPlanProtocol in inspect.getmro(SlotRunPlanResolver)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(IConfigAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for protocol in _REQUIRED_PROTOCOLS:
        for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction):
            signature = inspect.signature(getattr(protocol, name))
            assert signature.return_annotation is not inspect.Signature.empty, (
                f"{protocol.__name__}.{name} has no return"
            )
