# BACKLOG — Logging Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/logging/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `LOGGING-01`, the flush-completeness acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| LOGGING-01 | P1 | Ready | On Track | None | Add an acceptance scenario proving close flushes every record emitted before it into the log file. | 2026-10-05 |
| LOGGING-02 | P1 | Ready | At Risk | None | Add a regression proving a double bootstrap with one run id attaches no duplicate handler. | 2026-10-05 |
| LOGGING-03 | P2 | Ready | On Track | `JOBS-03` | Pin the status-file field set as a compatibility contract so a field removal is caught in CI. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| An interactive bootstrap attaches no standard-error handler | Automated | `modules/logging/tests/unit_observability_stderr.py` | stderr regression | 2026-10-05 |
| The run stamp attaches to records from worker threads | Automated | `modules/logging/tests/unit_observability_stderr.py` | thread stamp | 2026-10-05 |
| A failure category separates retried from terminal faults | Automated | `modules/logging/tests/unit_observability_stderr.py` | failure count | 2026-10-05 |
| A close flushes every record before returning | Gap | none yet | see `LOGGING-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `JOBS-03` owns the shared status-file field set both features publish.
- `SHARED-02` owns the pinned DOM helpers the quality report measures against.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/logging/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `LOGGING-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Per-subsystem span tracing stays outside the run lifecycle; only the run's quality report reads the counters.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
