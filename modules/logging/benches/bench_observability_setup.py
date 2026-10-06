"""Benchmark for the observability run-log handler cycle.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. The cycle runs against a temporary jobs directory
with a no-op status seam, so the benchmark needs no network and no live run.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.taxonomy_core_constant import DEFAULT_JOBS_DIR

pytestmark = pytest.mark.benchmark


def bench_attach_detach_run_log(iterations: int = 100) -> float:
    """Benchmark one attach/detach cycle for a per-run log handler."""
    setup = ObservabilitySetup(
        log_path=DEFAULT_JOBS_DIR,
        status_writer=MagicMock(),
        metrics=MetricsCounter(metrics_path=None),
    )

    start = time.perf_counter()
    for index in range(iterations):
        setup.attach_run_log(f"bench-{index}", f"run-{index}")
        setup.detach_run_log(f"run-{index}")
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_attach_detach_run_log() -> None:
    """Report benchmark results for the handler attach/detach cycle."""
    micros = bench_attach_detach_run_log()
    print(f"\n[BENCHMARK] attach+detach run log: {micros:.2f} µs/cycle")
    assert micros > 0
