"""Contract tests for the swarm capability's public seams.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.

The swarm feature has three capability seams — start, progress, cancel —
each sealed in its own protocol file. A single concrete class
(``SwarmRunner``) implements all three, so the runner's MRO carries every
one of them and a stub can implement only the seam it is exercising.
"""

from __future__ import annotations

import inspect

from modules.shared.src.swarm.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.swarm.contract_swarm_protocol import ISwarmCancelProtocol, ISwarmProgressProtocol, ISwarmStartProtocol
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

_SEAMS: tuple[type, frozenset[str]] = (
    (ISwarmStartProtocol, frozenset({"start"})),
    (ISwarmProgressProtocol, frozenset({"snapshot"})),
    (ISwarmCancelProtocol, frozenset({"cancel"})),
)


def test_runner_implements_every_swarm_seam() -> None:
    for seam, _ in _SEAMS:
        assert seam in inspect.getmro(SwarmRunner), f"SwarmRunner does not implement {seam.__name__}"


def test_orchestrator_implements_the_swarm_aggregate() -> None:
    assert ISwarmAggregate in inspect.getmro(SwarmOrchestrator)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(ISwarmAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_each_seam_declares_exactly_its_method_set() -> None:
    for seam, methods in _SEAMS:
        public = {name for name, _ in inspect.getmembers(seam, predicate=inspect.isfunction)}
        assert public == methods, f"{seam.__name__} declares {public}, expected {methods}"


def test_the_aggregate_exposes_browser_concurrency_as_a_property() -> None:
    assert isinstance(SwarmOrchestrator.browser_concurrency, property)
