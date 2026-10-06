# BACKLOG — Jobs Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/jobs/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `JOBS-01`, the zombie-reconciliation acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| JOBS-01 | P0 | Ready | At Risk | None | Add an acceptance scenario proving a pool restarted over zombie records reports every one terminal before its first poll. | 2026-10-05 |
| JOBS-02 | P1 | Ready | On Track | `MCP-01` | Specify the immediate backpressure envelope a saturated pool returns once the bounded-submission finding lands. | 2026-10-05 |
| JOBS-03 | P2 | Ready | On Track | None | Pin the status-file field set as a compatibility contract so a monitor field removal is caught in CI. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A pool at its pending ceiling rejects a submission | Automated | `modules/jobs/tests/unit_agent_job_backpressure.py` | queue rejection | 2026-10-05 |
| A folder input compiles to one attachment | Automated | `modules/jobs/tests/unit_folder_compiler.py` | folder compile | 2026-10-05 |
| An absent status file reads back as no mapping | Automated | `modules/jobs/tests/unit_capability_job_storage.py` | status read | 2026-10-05 |
| A restart reconciles every zombie record | Gap | none yet | see `JOBS-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `MCP-01` owns the MCP request/response boundary the backpressure envelope crosses.
- `SHARED-01` owns the session backup the job records reference.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/jobs/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `JOBS-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Cross-process pool sharing stays out of scope; each process owns its workers and its storage.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
