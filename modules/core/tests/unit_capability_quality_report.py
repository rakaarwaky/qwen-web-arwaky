"""Unit tests for defect-density tracking and the quality report (issue #340).

``MetricsCounter`` counts pipeline executions but never recorded *which* error
category caused a failure, so "which capability is most defective?" required
parsing ``app.jsonl`` by hand. These tests lock the four acceptance criteria:

- AC1: ``MetricsCounter.record_failure`` increments the per-category counter
- AC2: ``StatusFileWriter.write`` serialises ``failure_categories`` into status.json
- AC3: ``ObservabilitySetup.write_quality_report`` aggregates from app.jsonl
- AC4: ``CircuitBreaker.trip_category`` surfaces the dominant in-window category

``MetricsCounter`` and ``StatusFileWriter`` are standalone capabilities
(issue #359), so they are imported from their own modules and injected into
``ObservabilitySetup`` by the caller rather than built inside it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from modules.core.src.capabilities_metrics_counter import MetricsCounter
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_status_writer import StatusFileWriter, get_status_writer
from modules.shared.src.taxonomy_core_entity import CircuitBreaker
from modules.shared.src.taxonomy_core_error import (
    AuthRequiredError,
    ErrorCategory,
    NetworkTimeoutError,
    RateLimitError,
)
from modules.shared.src.utility_core_status import status_path_for


def _counter(tmp_path: Path) -> MetricsCounter:
    """Build a metrics counter backed by a per-test metrics file."""
    return MetricsCounter(metrics_path=tmp_path / "metrics.json")


def _setup(tmp_path: Path) -> ObservabilitySetup:
    """Build an observability stack with both collaborators injected (issue #359)."""
    return ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )


def _write_log(log_path: Path, lines: list[dict[str, Any]]) -> None:
    """Write *lines* as JSONL to *log_path*."""
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


# ── AC1: MetricsCounter tracks per-category errors ───────────────────────────


def test_error_category_exposes_the_canonical_set() -> None:
    """ErrorCategory.known() is the single source of truth for category names."""
    known = ErrorCategory.known()
    assert {"network", "auth", "rate_limit", "browser", "file_io", "other"} <= known
    assert "nonexistent" not in known
    for exc in (AuthRequiredError("x"), NetworkTimeoutError("x"), RateLimitError("x")):
        assert ErrorCategory.categorize(exc) in known


def test_record_failure_counts_per_category(tmp_path: Path) -> None:
    """Three network and two auth failures must appear in the counter."""
    mc = _counter(tmp_path)
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
    mc.record_failure("ValueError")
    assert mc.failure_counts() == {}
    assert "ValueError" not in mc.snapshot()


def test_failure_counts_survive_a_restart(tmp_path: Path) -> None:
    """Persisted category counts must load back from disk."""
    path = tmp_path / "metrics_reload.json"
    mc1 = MetricsCounter(metrics_path=path)
    mc1.record_failure("network")
    mc1.record_failure("network")
    mc2 = MetricsCounter(metrics_path=path)
    assert mc2.failure_counts().get("network", 0) == 2


def test_defect_density_is_errors_per_execution(tmp_path: Path) -> None:
    """Defect density = error_records / total_executions, exposed by the snapshot."""
    mc = _counter(tmp_path)
    for _ in range(5):
        mc.record_execution(True)
    for _ in range(2):
        mc.record_execution(False)
        mc.record_failure("network")
    mc.record_failure("browser")
    snap = mc.snapshot()
    assert int(snap["total_executions"]) == 7
    assert int(snap["successful_executions"]) == 5
    assert float(snap["success_rate"]) == pytest.approx(5 / 7, abs=1e-6)


# ── AC2: status.json includes failure_categories ─────────────────────────────


def test_status_file_includes_failure_categories(tmp_path: Path) -> None:
    """Monitoring tools read the breakdown straight from status.json."""
    writer = get_status_writer(tmp_path)
    writer.write(
        status="failed",
        mode="batch",
        headless=True,
        files_processed=10,
        files_failed=3,
        failure_categories={"network": 3, "auth": 1},
    )
    payload = writer.read()
    assert payload is not None
    assert payload["files_processed"] == 10
    assert payload["files_failed"] == 3
    cats: Mapping[str, Any] = payload["failure_categories"]
    assert cats["network"] == 3
    assert cats["auth"] == 1


def test_status_file_defaults_failure_categories_to_empty(tmp_path: Path) -> None:
    """The key is always present so consumers need no None handling."""
    writer = get_status_writer(tmp_path)
    writer.write()
    payload = writer.read()
    assert payload is not None
    assert payload.get("failure_categories", {}) == {}


def test_status_file_ranks_failure_categories_by_count(tmp_path: Path) -> None:
    """Higher-count categories must come first in the JSON output."""
    writer = get_status_writer(tmp_path)
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
    writer = get_status_writer(tmp_path)
    writer.write(status="failed", mode="batch", headless=True, failure_categories=raw)
    payload = writer.read()
    assert payload is not None
    assert payload["failure_categories"] == {}
    assert payload["status"] == "failed"


def test_status_writer_rejects_path_traversal_free_operation(tmp_path: Path) -> None:
    """A writer built by the helper targets the conventional status path only."""
    writer = get_status_writer(tmp_path)
    assert isinstance(writer, StatusFileWriter)
    writer.write(status="ok", mode="batch", headless=True, run_id="r1")
    assert (tmp_path / "status.json").exists()


# ── AC3: quality report from app.jsonl ────────────────────────────────────────


def test_quality_report_ranks_error_distribution(tmp_path: Path) -> None:
    """The report answers "which category fails most?" without reading the log."""
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
    out = _setup(tmp_path).write_quality_report(run_id="r-test")
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["run_id"] == "r-test"
    assert report["error_records"] == 4
    dist = report["error_distribution"]
    assert dist["network"] == 2
    assert dist["auth"] == 1
    assert dist["browser"] == 1
    assert list(dist) == ["network", "auth", "browser"]


def test_quality_report_reports_defect_density_per_execution(tmp_path: Path) -> None:
    """Defect density = error records / recorded executions."""
    app = tmp_path / "app.jsonl"
    app.write_text(
        json.dumps({"level": "error", "category": "network"}) + "\n",
        encoding="utf-8",
    )
    # The rolling 24h window prunes older events, so seed ten *current* successes.
    setup = _setup(tmp_path)
    for _ in range(10):
        setup.metrics.record_execution(True)
    out = setup.write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["defect_density"] == pytest.approx(0.1)


def test_quality_report_defect_density_is_one_per_execution_when_all_fail(tmp_path: Path) -> None:
    """A run where every execution also errored yields a density of 1.0."""
    _write_log(tmp_path / "app.jsonl", [{"level": "error", "event": "boom", "category": "network"}] * 4)
    setup = _setup(tmp_path)
    for success in (True, True, False, False):
        setup.metrics.record_execution(success)

    report = json.loads(setup.write_quality_report().read_text(encoding="utf-8"))
    assert report["error_records"] == 4
    assert report["defect_density"] == pytest.approx(1.0, abs=1e-6)
    assert report["executions"]["total_executions"] == 4


def test_quality_report_defect_density_is_null_without_executions(tmp_path: Path) -> None:
    """Cold start: no executions means no ratio, not a divide-by-zero."""
    (tmp_path / "app.jsonl").write_text(
        json.dumps({"level": "error", "category": "auth"}) + "\n",
        encoding="utf-8",
    )
    out = _setup(tmp_path).write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["defect_density"] is None
    assert report["error_distribution"] == {"auth": 1}


def test_quality_report_survives_a_missing_log(tmp_path: Path) -> None:
    """No log yet must yield an empty report, not an exception."""
    out = _setup(tmp_path / "empty_dir").write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_records"] == 0
    assert report["error_distribution"] == {}
    assert out.exists()


def test_quality_report_skips_truncated_and_non_json_lines(tmp_path: Path) -> None:
    """A crash mid-write leaves a partial final line; it must be skipped."""
    (tmp_path / "app.jsonl").write_text(
        json.dumps({"level": "error", "event": "a", "category": "browser"})
        + "\n"
        + "not valid json\n"
        + json.dumps({"level": "info"})
        + "\n"
        + json.dumps([1, 2, 3])
        + "\n"  # non-dict
        + '{"level": "error", "event": "trunca',
        encoding="utf-8",
    )
    out = _setup(tmp_path).write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_records"] == 1
    assert report["error_distribution"] == {"browser": 1}


def test_quality_report_buckets_uncategorized_errors_as_other(tmp_path: Path) -> None:
    """An error record with no category still shows up in the distribution."""
    (tmp_path / "app.jsonl").write_text(
        json.dumps({"level": "error", "category": "network"})
        + "\n"
        + json.dumps({"level": "error"})  # no category key → other
        + "\n"
        + json.dumps({"level": "critical"})  # critical, no category → other
        + "\n"
        + json.dumps({"level": "error", "category": "unknown_bucket"})  # not in known() → other
        + "\n",
        encoding="utf-8",
    )
    out = _setup(tmp_path).write_quality_report()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["error_distribution"] == {"network": 1, "other": 3}


# ── AC4: circuit breaker trip names the dominant error category ──────────────
#
# The concurrent categorised-failure behaviour of CircuitBreaker is exercised
# in modules/core/tests/unit_concurrency_guards.py, which drives the real
# entity from ten threads. These tests lock the single-threaded threshold
# interaction that the orchestrator guard depends on: the guard reads
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
