"""Reusable UAT fixtures for deterministic goal-linked acceptance exercises.

These fixtures support UAT-BA-009 through UAT-BA-016 in UAT.md.
They run deterministically without a live Qwen session and are used by
pytest in modules/*/tests/ as UAT evidence generators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Goal-to-Scenario Evidence Helpers ────────────────────────────────────────────


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format for exercise timestamps."""
    return datetime.now(timezone.utc).isoformat()


def _load_or_create_exercise_record(
    fixture_dir: Path,
    uat_id: str,
    goal: int,
    commit: str | None = None,
) -> dict[str, Any]:
    """Load or create the evidence record file for a UAT exercise."""
    record_file = fixture_dir / f"{uat_id}.json"
    if record_file.exists():
        try:
            return json.loads(record_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    record: dict[str, Any] = {
        "uat_id": uat_id,
        "goal": goal,
        "commit": commit,
        "environment": {"os": "linux", "python": "3.12"},
        "tier_region": None,
        "timestamps": {"started": utc_now_iso()},
        "run_ids": [],
        "exclusions": [],
        "measured_values": {},
        "redacted_evidence": "",
        "reviewer_approval": {"approved": False, "reviewer": None, "note": None},
        "release_disposition": "pending",
    }
    record_file.parent.mkdir(parents=True, exist_ok=True)
    record_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── Goal 2: Result / Run-Record Reconciliation ────────────────────────────────────


def reconcile_results(
    output_dir: Path,
    run_records: list[dict[str, Any]],
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-010: Verify 100% of successful runs have both a result file and a run record.

    Returns a record dict suitable for saving as evidence.
    """
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-010", goal=2, commit=commit)

    matched = 0
    unmatched: list[str] = []
    for rr in run_records:
        status = rr.get("status", "")
        if status not in ("completed", "successful"):
            continue
        output_file = output_dir / rr.get("output_file", "")
        if output_file.is_file() and rr.get("run_id"):
            matched += 1
        else:
            unmatched.append(rr.get("run_id", "unknown"))

    record["measured_values"] = {
        "total_successful_runs": sum(1 for rr in run_records if rr.get("status") in ("completed", "successful")),
        "matched": matched,
        "unmatched": unmatched,
        "match_rate": matched / max(sum(1 for rr in run_records if rr.get("status") in ("completed", "successful")), 1),
    }
    record["release_disposition"] = "passed" if record["measured_values"]["match_rate"] == 1.0 else "failed"
    (fixture_dir / "UAT-BA-010.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── Goal 3: CLI/MCP Parity for Three Workflows ────────────────────────────────────


@dataclass(frozen=True)
class WorkflowResult:
    """One workflow outcome: direct text, prompt file, or prompt+document."""

    workflow: str
    success: bool
    result_location: str
    error_reason: str | None = None


def check_cli_mcp_parity(
    cli_results: list[WorkflowResult],
    mcp_results: list[WorkflowResult],
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-011: Verify 3/3 workflows produce matching outcomes on CLI and MCP surfaces."""
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-011", goal=3, commit=commit)

    expected_workflows = ("direct", "file", "attachment")
    mismatches: list[str] = []
    for wf in expected_workflows:
        cli_res = next((r for r in cli_results if r.workflow == wf), None)
        mcp_res = next((r for r in mcp_results if r.workflow == wf), None)
        if cli_res is None or mcp_res is None:
            mismatches.append(f"{wf}: missing result on one surface")
        elif cli_res.success != mcp_res.success:
            mismatches.append(f"{wf}: success mismatch")
        elif cli_res.result_location != mcp_res.result_location:
            mismatches.append(f"{wf}: result_location mismatch")

    record["measured_values"] = {
        "workflows_checked": len(expected_workflows),
        "mismatches": mismatches,
        "parity": len(mismatches) == 0,
    }
    record["release_disposition"] = "passed" if record["measured_values"]["parity"] else "failed"
    (fixture_dir / "UAT-BA-011.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── Goal 4: Asynchronous p95 Acknowledgement ───────────────────────────────────────


def measure_async_p95(
    ack_durations_ms: list[float],
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-012: Measure p95 acknowledgement latency across 30 trials.

    The p95 is the 95th percentile of the sorted list (index int(0.95 * n)).
    For n=30: int(0.95 * 30) = 28, so the 29th value (0-indexed 28) in the
    sorted list is the p95.

    Returns the record dict; records the p95 calculation explicitly.
    """
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-012", goal=4, commit=commit)

    sorted_vals = sorted(ack_durations_ms)
    n = len(sorted_vals)
    if n == 0:
        record["measured_values"] = {"p95_ms": None, "trials": 0, "threshold_ms": 2000.0, "pass": False}
        record["release_disposition"] = "failed"
    else:
        p95_index = min(int(0.95 * n), n - 1)
        p95_ms = sorted_vals[p95_index]
        pass_ = p95_ms <= 2000.0
        record["measured_values"] = {
            "trials": n,
            "p95_index": p95_index,
            "p95_ms": p95_ms,
            "threshold_ms": 2000.0,
            "pass": pass_,
            "p95_calculation": f"p95 = sorted([{len(sorted_vals)} values])[{p95_index}] = {p95_ms} ms (<= 2000 ms threshold)",
        }
        record["release_disposition"] = "passed" if pass_ else "failed"

    (fixture_dir / "UAT-BA-012.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── Goal 5: Ten-Run Fault Isolation ────────────────────────────────────────────────


def check_ten_run_isolation(
    run_statuses: dict[str, str],
    forced_failure_id: str,
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-013: Verify 9/9 unaffected runs reach terminal state despite 1 forced failure.

    *run_statuses* maps run_id -> terminal state string (e.g. "completed", "failed").
    """
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-013", goal=5, commit=commit)

    terminal_states = {"completed", "failed", "timed_out", "cancelled"}
    unaffected = {k: v for k, v in run_statuses.items() if k != forced_failure_id}
    unaffected_reached = sum(1 for v in unaffected.values() if v in terminal_states)

    record["measured_values"] = {
        "total_runs": len(run_statuses),
        "forced_failure": forced_failure_id,
        "unaffected_runs": len(unaffected),
        "unaffected_reached_terminal": unaffected_reached,
        "isolation_held": unaffected_reached == len(unaffected) and len(unaffected) == 9,
    }
    record["release_disposition"] = "passed" if record["measured_values"]["isolation_held"] else "failed"
    (fixture_dir / "UAT-BA-013.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── BA-2-001: Session Health Verdict Classification ────────────────────────────────


def record_health_verdict_exercise(
    verdicts: list[dict[str, Any]],
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-015: Record session health verdict classification evidence.

    Each entry in *verdicts* is a dict with keys:
        - session_name: str
        - expected_status: str  (ACTIVE | LIMITED | AUTH_REQUIRED)
        - observed_status: str
        - reason: str | None
        - recovery_action: str | None
    """
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-015", goal=2, commit=commit)

    mismatched = [v["session_name"] for v in verdicts if v.get("expected_status") != v.get("observed_status")]
    record["measured_values"] = {
        "verdicts_checked": len(verdicts),
        "mismatched": mismatched,
        "all_correct": not mismatched,
    }
    record["release_disposition"] = "passed" if record["measured_values"]["all_correct"] else "failed"
    (fixture_dir / "UAT-BA-015.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


# ─── BA-2-002: Rotation Outcome Evidence ────────────────────────────────────────────


def record_rotation_outcome_exercise(
    outcomes: dict[str, dict[str, Any]],
    fixture_dir: Path,
    commit: str | None = None,
) -> dict[str, Any]:
    """UAT-BA-016: Record rotation outcome evidence for all pool conditions.

    *outcomes* maps pool_condition -> {"outcome": str, "reason": str, "pass": bool}
    Pool conditions: "empty_pool", "single_limited", "all_limited",
                     "excluded_all", "mixed"
    """
    record = _load_or_create_exercise_record(fixture_dir, "UAT-BA-016", goal=2, commit=commit)

    failures = [k for k, v in outcomes.items() if not v.get("pass", False)]
    record["measured_values"] = {
        "pool_conditions_checked": len(outcomes),
        "failed_conditions": failures,
        "all_passed": not failures,
    }
    record["release_disposition"] = "passed" if record["measured_values"]["all_passed"] else "failed"
    (fixture_dir / "UAT-BA-016.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
