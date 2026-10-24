# BACKLOG — Jobs Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/jobs/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Next Action: None. `JOBS-01` shipped on 2026-10-22; next open item is `JOBS-02`.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| JOBS-01 | P0 | Done | None | None — zombie reconciliation accepts a `dead_pid OR stale heartbeat` rule; proven by `acceptance_job_zombie_reconciliation.py`. | 2026-10-22 | FR-JOBS-001 |
| JOBS-02 | P1 | Done | `MCP-01` | None — the saturated-pool envelope shipped: MCP `QUEUE_FULL` with `retry_after_sec`/`queue_depth`, CLI `cli-429`; covered by `unit_mcp_response_envelope.py` and `unit_surface_cli_jobs_command.py`. | 2026-10-22 | FR-JOBS-001, FR-JOBS-002 |
| JOBS-03 | P2 | Done | `LOGGING-03` | None — single owner: `modules/shared/tests/contract_status_schema.py` pins the schema-version-2 key set (base + fully-populated + omitted-optionals); cross-referenced by LOGGING-03. | 2026-10-22 | FR-JOBS-002 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A pool at its pending ceiling rejects a submission | Automated | `modules/jobs/tests/unit_agent_job_backpressure.py` | queue rejection | 2026-10-05 |
| An absent status file reads back as no mapping | Automated | `modules/jobs/tests/unit_capability_job_storage.py` | status read | 2026-10-05 |
| A restart reconciles every zombie record | Automated | `modules/jobs/tests/acceptance_job_zombie_reconciliation.py` | `test_acceptance_seeded_zombies_are_terminal_before_the_first_poll`, `test_acceptance_a_recycled_pid_is_reconciled_by_heartbeat_staleness` | 2026-10-22 |

## Blockers

None.

## Dependencies

- `MCP-01` owns the MCP request/response boundary the backpressure envelope crosses.
- `SHARED-01` owns the session backup the job records reference.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/jobs/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | All 3 scenarios mapped; the former `JOBS-01` gap closed on 2026-10-22. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-14 | FRD requirements matched to the two declared capability seams; folder compilation left to the feature whose contract declares it. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
