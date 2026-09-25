"""Unit tests for defect-density tracking and quality report (issue #340).

Verifies the four acceptance criteria:

- AC1: ``MetricsCounter.record_failure`` increments the per-category counter
- AC2: ``StatusFileWriter.write`` serialises ``failure_categories`` into status.json
- AC3: ``ObservabilitySetup.write_quality_report`` aggregates from app.jsonl
- AC4: ``CircuitBreaker.trip_category`` surfaces the dominant in-window category
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from modules.core.src.capabilities_observability_setup import (
    MetricsCounter,
    ObservabilitySetup,
    get_status_writer,
)
from modules.shared.src.taxonomy_core_entity import CircuitBreaker
from modules.shared.src.taxonomy_core_error import ErrorCategory

# ── AC1: MetricsCounter tracks per-category errors ───────────────────────────


def test_error_category_exposes_the_canonical_set() -> None:
    """ErrorCategory.known() must cover every rule-defined bucket plus 'other'."""
    assert "network" in ErrorCategory.known()
    assert "auth" in ErrorCategory.known()
    assert "file_io" in ErrorCategory.known()
    assert "other" in ErrorCategory.known()
    assert "nonexistent" not in ErrorCategory.known()


def test_record_failure_counts_per_category(tmp_path: Path) -> None:
    """Three network and two auth failures must appear in the counter."""
    mc = MetricsCounter(metrics_path=tmp_path / "metrics.json")
    mc.record_failure("network")
    mc.record_failure("network")
    mc.record_failure("network")
    mc.record_failure("auth")
    mc.record_failure("auth")
    counts = mc.failure_counts()
    assert counts.get("network", 0) == 3
    assert counts.get("auth", 0) == 2
    assert counts.get("browser", 0) == 0


def test_record_failure_rejects_unknown_category(tmp_path: Path) -> None:
    """An unknown string must be silently dropped so the counter has no unbounded keys."""
    mc = MetricsCounter(metrics_path=tmp_path / "metrics_unknown.json")
    mc.record_failure("completely_unexpected_xyz")
    assert mc.failure_counts() == {}


def test_failure_counts_survive_a_restart(tmp_path: Path) -> None:
    """Persisted category counts must load back from disk."""
    p = tmp_path / "metrics_reload.json"
    mc1 = MetricsCounter(metrics_path=p)
    mc1.record_failure("network")
    mc1.record_failure("network")
    mc2 = MetricsCounter(metrics_path=p)
    assert mc2.failure_counts().get("network", 0) == 2


def test_defect_density_is_errors_per_execution(tmp_path: Path) -> None:
    """A helper property — defect density = error_records / total_executions."""
    mc = MetricsCounter(metrics_path=tmp_path / "density.json")
    for _ in range(5):
        mc.record_execution(True)
    for _ in range(2):
        mc.record_execution(False)
        mc.record_failure("network")
    snap = mc.snapshot()
    assert int(snap["total_executions"]) == 7
    assert int(snap["successful_executions"]) == 5


# ── AC2: status.json includes failure_categories ─────────────────────────────


def test_status_file_includes_failure_categories(tmp_path: Path) -> None:
    writer = get_status_writer(tmp_path / "status.json")
    writer.write(failure_categories={"network": 3, "auth": 1})
    payload = writer.read()
    assert payload is not None
    cats: Mapping[str, Any] = payload.get("failure_categories", {})
    assert cats["network"] == 3
    assert cats["auth"] == 1


def test_status_file_defaults_failure_categories_to_empty(tmp_path: Path) -> None:
    writer = get_status_writer(tmp_path / "status_empty.json")
    writer.write()
    payload = writer.read()
    assert payload is not None
    assert payload.get("failure_categories", {}) == {}


def test_status_file_ranks_failure_categories_by_count(tmp_path: Path) -> None:
    """Higher-count categories must come first in the JSON output."""
    writer = get_status_writer(tmp_path / "status_ranked.json")
    writer.write(failure_categories={"auth": 5, "network": 10, "parsing": 2})
    payload = writer.read()
    assert payload is not None
    cats: list[tuple[str, int]] = list(payload["failure_categories"].items())
    assert cats[0] == ("network", 10)
    assert cats[1] == ("auth", 5)
    assert cats[2] == ("parsing", 2)


@pytest.mark.parametrize(
    "raw",
    [None, {}, [], "network", [("bad")], [("network", "many")]],
)
def test_malformed_failure_categories_never_corrupt_status_json(raw: Any, tmp_path: Path) -> None:
    """Bad shapes are dropped, leaving the rest of status.json intact."""
    writer = get_status_writer(tmp_path / "status_bad.json")
    writer.write(failure_categories=raw)
    payload = writer.read()
    assert payload is not None
    assert isinstance(payload["failure_categories"], dict)


def test_status_writer_rejects_path_traversal_free_operation(tmp_path: Path) -> None:
    """Status writer lives entirely under the caller's log directory."""
    writer = get_status_writer(tmp_path / "log")
    writer.write(status="ok", mode="batch", headless=True, run_id="r1")
    assert (tmp_path / "log" / "status.json").exists()


# ── AC3: quality report from app.jsonl ────────────────────────────────────────


def test_quality_report_ranks_error_distribution(tmp_path: Path) -> None:
    app = tmp_path / "app.jsonl"
    app.write_text(
        "\n".join(
            [
                json.dumps({"level": "error", "category": "network", "msg": "timeout"}) + "\n",
                json.dumps({"level": "error", "category": "network", "msg": "dns fail"}) + "\n",
                json.dumps({"level": "error", "category": "auth", "msg": "403"}) + "\n",
                json.dumps({"level": "info", "category": None, "msg": "skip me"}) + "\n",
                json.dumps({"level": "critical", "category": "browser", "msg": "crash"}) + "\n",
            ]
        ),
        encoding="utf-8",
    )
    setup = ObservabilitySetup(log_path=tmp_path)
    out = setup.write_quality_report(run_id="r-test")
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_records"] == 4
    dist = report["error_distribution"]
    assert dist["network"] == 2
    assert dist["auth"] == 1
    assert dist["browser"] == 1


def test_quality_report_reports_defect_density_per_execution(tmp_path: Path) -> None:
    app = tmp_path / "app.jsonl"
    app.write_text(
        json.dumps({"level": "error", "category": "network"}) + "\n",
        encoding="utf-8",
    )
    # The rolling 24h window prunes older events, so seed ten *current* successes.
    mc = MetricsCounter(metrics_path=tmp_path / "metrics.json")
    for _ in range(10):
        mc.record_execution(True)
    setup = ObservabilitySetup(log_path=tmp_path)
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["defect_density"] == pytest.approx(0.1)


def test_quality_report_defect_density_is_null_without_executions(tmp_path: Path) -> None:
    app = tmp_path / "app.jsonl"
    app.write_text(json.dumps({"level": "error"}) + "\n", encoding="utf-8")
    setup = ObservabilitySetup(log_path=tmp_path)
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["defect_density"] is None


def test_quality_report_survives_a_missing_log(tmp_path: Path) -> None:
    setup = ObservabilitySetup(log_path=tmp_path / "empty_dir")
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_records"] == 0
    assert report["error_distribution"] == {}
    assert out.exists()


def test_quality_report_skips_truncated_and_non_json_lines(tmp_path: Path) -> None:
    app = tmp_path / "app.jsonl"
    app.write_text(
        json.dumps({"level": "error", "category": "network"}) + "\n"
        "not valid json\n" + json.dumps({"level": "info"}) + "\n" + json.dumps([1, 2, 3]) + "\n",  # non-dict
        encoding="utf-8",
    )
    setup = ObservabilitySetup(log_path=tmp_path)
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_records"] == 1
    assert report["error_distribution"] == {"network": 1}


def test_quality_report_buckets_uncategorized_errors_as_other(tmp_path: Path) -> None:
    app = tmp_path / "app.jsonl"
    app.write_text(
        json.dumps({"level": "error", "category": "network"})
        + "\n"
        + json.dumps({"level": "error"})
        + "\n"  # no category key → other
        + json.dumps({"level": "error", "category": "unknown_bucket"})
        + "\n",  # not in known() → other
        encoding="utf-8",
    )
    setup = ObservabilitySetup(log_path=tmp_path)
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_distribution"] == {"network": 1, "other": 2}


# ── AC4: circuit breaker trip names the dominant error category ──────────────
#
# The concurrent categorised-failure behaviour of CircuitBreaker is exercised
# in modules/core/tests/unit_concurrency_guards.py, which drives the real
# entity from ten threads. These two tests lock the single-threaded
# threshold interaction that the orchestrator guard depends on: the guard reads
# ``is_tripped`` before naming a category, so a breaker that has NOT yet
# reached its threshold must report no category.


def test_circuit_breaker_below_threshold_reports_no_category() -> None:
    """A breaker that has not tripped must not claim a dominant category."""
    cb = CircuitBreaker(threshold=3, window_sec=60)
    cb.record_failure()

    assert not cb.is_tripped
    assert cb.trip_category is None


def test_circuit_breaker_trips_exactly_at_threshold() -> None:
    """``AgentJobOrchestrator`` gates on ``is_tripped``, so the boundary is exact."""
    cb = CircuitBreaker(threshold=3, window_sec=60)
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_tripped
    cb.record_failure()
    assert cb.is_tripped


def test_circuit_breaker_success_resets_the_window() -> None:
    """A success clears the window, so a single late failure cannot trip alone."""
    cb = CircuitBreaker(threshold=3, window_sec=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()

    assert not cb.is_tripped
