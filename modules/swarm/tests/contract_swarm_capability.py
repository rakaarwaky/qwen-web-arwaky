"""Contract tests for the swarm capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.contract_swarm_protocol import ISwarmProtocol
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

_REQUIRED_PROTOCOL_METHODS: frozenset[str] = frozenset({"start", "snapshot", "cancel"})


def test_runner_implements_the_swarm_protocol() -> None:
    assert ISwarmProtocol in inspect.getmro(SwarmRunner)


def test_orchestrator_implements_the_swarm_aggregate() -> None:
    assert ISwarmAggregate in inspect.getmro(SwarmOrchestrator)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(ISwarmAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_protocol_declares_exactly_the_sealed_method_set() -> None:
    public = {name for name, _ in inspect.getmembers(ISwarmProtocol, predicate=inspect.isfunction)}
    assert public == set(_REQUIRED_PROTOCOL_METHODS)


def test_the_aggregate_exposes_browser_concurrency_as_a_property() -> None:
    assert isinstance(SwarmOrchestrator.browser_concurrency, property)
