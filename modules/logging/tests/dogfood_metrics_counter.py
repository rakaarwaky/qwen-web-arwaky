"""Dogfood tests for the metrics counter against a real metrics file.

These increment and read counters backed by a file under a temporary
directory, so the persistence and the snapshot purity are exercised against
the filesystem rather than a stub.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.logging.src.capabilities_metrics_counter import MetricsCounter


def test_dogfood_an_incremented_counter_reads_back(tmp_path: Path) -> None:
    metrics = MetricsCounter(metrics_path=tmp_path / "metrics.json")

    metrics.increment("dogfood_runs")
    metrics.increment("dogfood_runs")

    assert metrics.get("dogfood_runs") == 2


def test_dogfood_a_read_does_not_mutate_the_counter(tmp_path: Path) -> None:
    metrics = MetricsCounter(metrics_path=tmp_path / "metrics.json")
    metrics.increment("dogfood_runs")

    first = metrics.snapshot()
    second = metrics.snapshot()

    assert first == second


def test_dogfood_counters_persist_to_the_metrics_file(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    metrics = MetricsCounter(metrics_path=path)
    metrics.increment("dogfood_persisted")

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["counters"]["dogfood_persisted"] == 1


def test_dogfood_a_known_failure_category_is_counted_separately(tmp_path: Path) -> None:
    metrics = MetricsCounter(metrics_path=tmp_path / "metrics.json")

    metrics.record_failure("response_timeout")
    metrics.record_execution(success=False)

    counts = metrics.failure_counts()
    assert counts.get("response_timeout") == 1


def test_dogfood_an_unknown_failure_category_is_ignored(tmp_path: Path) -> None:
    """An unbounded category name would let a raw exception type inflate
    the defect counts, so the taxonomy is the only accepted vocabulary."""
    metrics = MetricsCounter(metrics_path=tmp_path / "metrics.json")

    metrics.record_failure("SomethingNobodyCategorised")

    assert metrics.failure_counts() == {}
