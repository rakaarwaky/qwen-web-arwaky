# BACKLOG — Logging Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/logging/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Next Action: None. Both LOGGING-01 and LOGGING-02 are Done.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| LOGGING-01 | P1 | Done | None | Add an acceptance scenario proving close flushes every record emitted before it into the log file. | 2026-10-24 | FR-LOGGING-001 |
| LOGGING-02 | P1 | Done | None | None — pinned by `modules/logging/tests/unit_observability_bootstrap_idempotency.py` (double bootstrap, one run id, singular handlers). | 2026-10-24 | FR-LOGGING-001, FR-LOGGING-002 |
| LOGGING-03 | P2 | Done | `JOBS-03` | None — closed into the single contract owner `modules/shared/tests/contract_status_schema.py` (see JOBS-03). | 2026-10-22 | FR-LOGGING-002 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| An interactive bootstrap attaches no standard-error handler | Automated | `modules/logging/tests/unit_observability_stderr.py` | stderr regression | 2026-10-05 |
| The run stamp attaches to records from worker threads | Automated | `modules/logging/tests/unit_observability_stderr.py` | thread stamp | 2026-10-05 |
| A failure category separates retried from terminal faults | Automated | `modules/logging/tests/unit_observability_stderr.py` | failure count | 2026-10-05 |
| A close flushes every record before returning | Automated | `modules/logging/tests/acceptance_logging_flush.py` | close flush | 2026-10-24 |
| A bootstrap run twice with the same run id attaches no duplicate handler | Automated | `modules/logging/tests/unit_observability_bootstrap_idempotency.py` | `LOGGING-02` regression | 2026-10-24 |

## Blockers

None.

## Dependencies

- `JOBS-03` owns the shared status-file field set both features publish.
- `SHARED-02` owns the pinned DOM helpers the quality report measures against.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/logging/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 4 of 4 scenarios mapped; none left open as a gap. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-24 | `LOGGING-02` to Done: handler dedup in `capabilities_observability_setup.py` plus regression in `unit_observability_bootstrap_idempotency.py`. | rakaarwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
