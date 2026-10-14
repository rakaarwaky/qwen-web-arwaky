"""Contract tests for the swarm capability's public seams.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.

The swarm feature has three consumer seams — start, progress, cancel —
each sealed in its own protocol file and implemented by its own
capability file, plus the shared registry behind them. A test can therefore
inject a stub that implements only the seam it is exercising.
"""

from __future__ import annotations

import inspect

from modules.shared.src.swarm.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.swarm.contract_swarm_protocol import (
    ISwarmCancelProtocol,
    ISwarmProgressProtocol,
    ISwarmRegistryProtocol,
    ISwarmStartProtocol,
)
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_cancel import SwarmCancelRunner
from modules.swarm.src.capabilities_swarm_progress import SwarmProgressRunner
from modules.swarm.src.capabilities_swarm_registry import SwarmRegistry
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

_SEAMS: tuple[type, frozenset[str]] = (
    (ISwarmStartProtocol, frozenset({"start"})),
    (ISwarmProgressProtocol, frozenset({"snapshot"})),
    (ISwarmCancelProtocol, frozenset({"cancel"})),
)

#: The one capability that implements each seam.
_IMPLEMENTORS: dict[type, type] = {
    ISwarmStartProtocol: SwarmRunner,
    ISwarmProgressProtocol: SwarmProgressRunner,
    ISwarmCancelProtocol: SwarmCancelRunner,
    ISwarmRegistryProtocol: SwarmRegistry,
}


def _implemented_protocols(implementation: type) -> list[type]:
    """Return every seam protocol *implementation* inherits."""
    return [seam for seam in _IMPLEMENTORS if seam in inspect.getmro(implementation)]


def test_every_seam_has_its_own_implementor() -> None:
    for seam, implementation in _IMPLEMENTORS.items():
        assert seam in inspect.getmro(implementation), f"{implementation.__name__} does not implement {seam.__name__}"


def test_no_capability_implements_more_than_one_seam() -> None:
    """AES403: one protocol per capability file, so the seams stay separable."""
    for seam, implementation in _IMPLEMENTORS.items():
        implemented = _implemented_protocols(implementation)
        assert implemented == [seam], (
            f"{implementation.__name__} implements {implemented}, expected only {seam.__name__}"
        )


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
