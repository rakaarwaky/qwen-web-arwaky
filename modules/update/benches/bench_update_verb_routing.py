"""Benchmark for update-verb routing through UpdateOrchestrator.execute (current_version path over a stubbed updater).

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. The routing path is pure, so the benchmark needs
no network, no subprocess, and no installed release.
"""

from __future__ import annotations

import time

import pytest

from modules.shared.src.taxonomy_update_vo import UpdateRequest
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator

pytestmark = pytest.mark.benchmark


def _orchestrator() -> UpdateOrchestrator:
    """Return an orchestrator over a stub manager that never upgrades."""
    from unittest.mock import MagicMock

    manager = MagicMock()
    manager.current_version.return_value = "0.0.0"
    return UpdateOrchestrator(manager, MagicMock())


def bench_verb_routing(iterations: int = 2000) -> float:
    """Benchmark one read-only verb routed through the orchestrator."""
    orchestrator = _orchestrator()
    request = UpdateRequest(verb="current_version")

    # Verify routing correctness before measuring; per-iteration asserts would
    # add comparison overhead to the timed region.
    response = orchestrator.execute(request)
    assert response.error is None, f"unexpected verb routing error: {response.error!r}"
    assert response.version is not None

    start = time.perf_counter()
    for _ in range(iterations):
        orchestrator.execute(request)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_verb_routing() -> None:
    """Report benchmark results for one routed update verb."""
    micros = bench_verb_routing()
    print(f"\n[BENCHMARK] update verb routing: {micros:.2f} µs/call")
    assert micros > 0
