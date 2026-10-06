"""Benchmark for the swarm fan-out snapshot.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. The snapshot runs against a stub runner, so the
benchmark needs no browser build, no network, and no live session.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from modules.shared.src.taxonomy_swarm_vo import SwarmRequest
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator

pytestmark = pytest.mark.benchmark


def _orchestrator() -> SwarmOrchestrator:
    """Return an orchestrator over a stub runner that reports no legs."""
    runner = MagicMock()
    runner.snapshot.return_value = None
    return SwarmOrchestrator(runner=runner, observability=MagicMock())


def bench_snapshot(iterations: int = 2000) -> float:
    """Benchmark one snapshot read against a stub runner."""
    orchestrator = _orchestrator()

    start = time.perf_counter()
    for _ in range(iterations):
        orchestrator.execute(SwarmRequest(verb="snapshot", swarm_id="bench-0001"))
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_snapshot() -> None:
    """Report benchmark results for one snapshot read."""
    micros = bench_snapshot()
    print(f"\n[BENCHMARK] swarm snapshot: {micros:.2f} µs/call")
    assert micros > 0
