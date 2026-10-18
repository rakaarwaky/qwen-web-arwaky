"""UAT fixtures tests (BA-5-001).

These tests run the deterministic UAT fixtures from tests/uat_fixtures.py
against controlled inputs and verify the recorded evidence structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.uat_fixtures import (
    WorkflowResult,
    check_cli_mcp_parity,
    check_ten_run_isolation,
    measure_async_p95,
    reconcile_results,
    record_health_verdict_exercise,
    record_reliability_sample,
    record_rotation_outcome_exercise,
)


def test_reconcile_results_all_match(tmp_path: Path) -> None:
    """UAT-BA-010: 100% reconciliation when all successful runs have both artifacts."""
    run_records = [
        {"run_id": "r1", "status": "completed", "output_file": "out1.md"},
        {"run_id": "r2", "status": "completed", "output_file": "out2.md"},
        {"run_id": "r3", "status": "failed", "output_file": "out3.md"},
    ]
    for rid in ("out1.md", "out2.md"):
        (tmp_path / rid).write_text("result")

    record = reconcile_results(tmp_path, run_records, tmp_path)
    assert record["measured_values"]["match_rate"] == 1.0
    assert record["release_disposition"] == "passed"


def test_reconcile_results_missing_output_fails(tmp_path: Path) -> None:
    """UAT-BA-010: reconciliation fails when an output file is missing."""
    run_records = [
        {"run_id": "r1", "status": "completed", "output_file": "out1.md"},
    ]
    record = reconcile_results(tmp_path, run_records, tmp_path)
    assert record["release_disposition"] == "failed"


def test_cli_mcp_parity_all_match(tmp_path: Path) -> None:
    """UAT-BA-011: 3/3 workflows produce matching CLI and MCP outcomes."""
    cli_results = [
        WorkflowResult("direct", True, "/out/direct.md"),
        WorkflowResult("file", True, "/out/file.md"),
        WorkflowResult("attachment", True, "/out/att.md"),
    ]
    mcp_results = [
        WorkflowResult("direct", True, "/out/direct.md"),
        WorkflowResult("file", True, "/out/file.md"),
        WorkflowResult("attachment", True, "/out/att.md"),
    ]
    record = check_cli_mcp_parity(cli_results, mcp_results, tmp_path)
    assert record["measured_values"]["parity"] is True
    assert record["release_disposition"] == "passed"


def test_cli_mcp_parity_mismatch(tmp_path: Path) -> None:
    """UAT-BA-011: parity fails when result locations differ between surfaces."""
    cli_results = [WorkflowResult("direct", True, "/out/cli.md")]
    mcp_results = [WorkflowResult("direct", True, "/out/mcp.md")]
    record = check_cli_mcp_parity(cli_results, mcp_results, tmp_path)
    assert record["measured_values"]["parity"] is False
    assert record["release_disposition"] == "failed"


def test_async_p95_within_threshold(tmp_path: Path) -> None:
    """UAT-BA-012: p95 of 30 trials ≤ 2000 ms → passed."""
    # 30 values all below threshold
    durations = [
        100.0,
        150.0,
        200.0,
        300.0,
        400.0,
        500.0,
        600.0,
        700.0,
        800.0,
        900.0,
        1000.0,
        1100.0,
        1200.0,
        1300.0,
        1400.0,
        1500.0,
        1600.0,
        1700.0,
        1800.0,
        1900.0,
        1950.0,
        1970.0,
        1990.0,
        1999.0,
        2000.0,
        2000.0,
        2000.0,
        2000.0,
        2000.0,
        2000.0,
    ]
    record = measure_async_p95(durations, tmp_path)
    assert record["measured_values"]["pass"] is True
    assert record["measured_values"]["trials"] == 30
    assert "p95_calculation" in record["measured_values"]


def test_async_p95_exceeds_threshold(tmp_path: Path) -> None:
    """UAT-BA-012: p95 > 2000 ms → failed."""
    durations = [2500.0] * 30
    record = measure_async_p95(durations, tmp_path)
    assert record["measured_values"]["pass"] is False
    assert record["release_disposition"] == "failed"


def test_tenth_run_isolation_passes(tmp_path: Path) -> None:
    """UAT-BA-013: 9/9 unaffected runs reach terminal state when 1 forced failure.

    run_statuses maps ALL 10 run IDs; the forced-failure run is one of them,
    and the other 9 must reach a terminal state.
    """
    run_statuses = {f"run-{i}": "completed" for i in range(1, 11)}
    record = check_ten_run_isolation(run_statuses, "run-1", tmp_path)
    assert record["measured_values"]["isolation_held"] is True
    assert record["release_disposition"] == "passed"


def test_tenth_run_isolation_fails_when_unaffected_run_incomplete(tmp_path: Path) -> None:
    """UAT-BA-013: isolation fails when an unaffected run is still running."""
    run_statuses = {f"run-{i}": ("running" if i == 5 else "completed") for i in range(1, 11)}
    record = check_ten_run_isolation(run_statuses, "run-1", tmp_path)
    assert record["measured_values"]["isolation_held"] is False


def test_health_verdict_exercise_all_correct(tmp_path: Path) -> None:
    """UAT-BA-015: all verdicts classified correctly."""
    verdicts = [
        {"session_name": "s1", "expected_status": "active", "observed_status": "active"},
        {"session_name": "s2", "expected_status": "limited", "observed_status": "limited"},
        {"session_name": "s3", "expected_status": "auth_required", "observed_status": "auth_required"},
    ]
    record = record_health_verdict_exercise(verdicts, tmp_path)
    assert record["measured_values"]["all_correct"] is True


def test_health_verdict_exercise_with_mismatch(tmp_path: Path) -> None:
    """UAT-BA-015: mismatched verdicts cause the exercise to fail."""
    verdicts = [
        {"session_name": "s1", "expected_status": "active", "observed_status": "limited"},
    ]
    record = record_health_verdict_exercise(verdicts, tmp_path)
    assert record["measured_values"]["all_correct"] is False


def test_rotation_outcome_exercise_all_pass(tmp_path: Path) -> None:
    """UAT-BA-016: all pool conditions produce the expected outcome."""
    outcomes: dict[str, Any] = {
        "empty_pool": {"outcome": "no_eligible_session", "reason": "empty_pool", "pass": True},
        "single_limited": {"outcome": "no_eligible_session", "reason": "all_sessions_limited", "pass": True},
        "all_limited": {"outcome": "no_eligible_session", "reason": "all_sessions_limited", "pass": True},
        "excluded_all": {"outcome": "no_eligible_session", "reason": "all_sessions_excluded", "pass": True},
        "mixed": {"outcome": "success", "reason": None, "pass": True},
    }
    record = record_rotation_outcome_exercise(outcomes, tmp_path)
    assert record["measured_values"]["all_passed"] is True
    assert record["release_disposition"] == "passed"


def test_rotation_outcome_exercise_with_failure(tmp_path: Path) -> None:
    """UAT-BA-016: a failing pool condition causes the exercise to fail."""
    outcomes: dict[str, Any] = {
        "empty_pool": {"outcome": "no_eligible_session", "reason": "empty_pool", "pass": True},
        "mixed": {"outcome": "success", "reason": None, "pass": False},
    }
    record = record_rotation_outcome_exercise(outcomes, tmp_path)
    assert record["measured_values"]["all_passed"] is False
    assert record["release_disposition"] == "failed"


# ─── UAT-BA-009: Reliability Sample ──────────────────────────────────────────────


def test_reliability_sample_unapproved_protocol_raises(tmp_path: Path) -> None:
    """UAT-BA-009: an unapproved sampling protocol must fail fast (gate)."""
    with pytest.raises(ValueError, match="approved sampling protocol"):
        record_reliability_sample(
            successes=99,
            exclusions=[],
            protocol_approval={"approved": False},
            fixture_dir=tmp_path,
        )


def test_reliability_sample_missing_protocol_approval_raises(tmp_path: Path) -> None:
    """UAT-BA-009: a missing protocol approval record must fail fast."""
    with pytest.raises(ValueError, match="approved sampling protocol"):
        record_reliability_sample(
            successes=99,
            exclusions=[],
            protocol_approval={},
            fixture_dir=tmp_path,
        )


def test_reliability_sample_clean_99_100_passes(tmp_path: Path) -> None:
    """UAT-BA-009: 99/100 with one reasoned exclusion → passed."""
    record = record_reliability_sample(
        successes=99,
        exclusions=[{"run_id": "r42", "reason": "AUTH_REQUIRED"}],
        protocol_approval={"approved": True, "reviewer": "qa"},
        fixture_dir=tmp_path,
    )
    assert record["measured_values"]["success_rate"] == 0.99
    assert record["measured_values"]["excluded_runs"] == 1
    assert record["release_disposition"] == "passed"


def test_reliability_sample_98_100_fails(tmp_path: Path) -> None:
    """UAT-BA-009: 98/100 success rate is below the 99/100 threshold → failed."""
    record = record_reliability_sample(
        successes=98,
        exclusions=[
            {"run_id": "r7", "reason": "TIMEOUT"},
            {"run_id": "r13", "reason": "NETWORK"},
        ],
        protocol_approval={"approved": True, "reviewer": "qa"},
        fixture_dir=tmp_path,
    )
    assert record["measured_values"]["success_rate"] == 0.98
    assert record["release_disposition"] == "failed"


def test_reliability_sample_exclusion_without_reason_fails(tmp_path: Path) -> None:
    """UAT-BA-009: an exclusion lacking a recorded reason invalidates the sample."""
    record = record_reliability_sample(
        successes=99,
        exclusions=[{"run_id": "r9"}],  # no reason key
        protocol_approval={"approved": True, "reviewer": "qa"},
        fixture_dir=tmp_path,
    )
    assert record["release_disposition"] == "failed"
