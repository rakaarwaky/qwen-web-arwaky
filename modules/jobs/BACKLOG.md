# BACKLOG — Jobs Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-25

## Progress Overview

The jobs feature is Done. `uv run python -m pytest modules/jobs/tests/ -v` → 100 passed (2026-10-25, commit `9685d84`) covers background-job execution and the per-run status-file envelope. No row is in progress or blocked; every backlog entry is Done.

## Backlog Status

### FR-JOBS-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/jobs/tests/acceptance_job_zombie_reconciliation.py -v` → 7 passed (2026-10-25, commit `9685d84`). Zombie reconciliation accepts a `dead_pid OR stale heartbeat` rule. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-JOBS-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/jobs/tests/ -v` → 100 passed (2026-10-25, commit `9685d84`); the saturated-pool envelope ships MCP `QUEUE_FULL` with `retry_after_sec`/`queue_depth` and CLI `cli-429`, covered by `unit_mcp_response_envelope.py` and `unit_surface_cli_jobs_command.py`. The status-file schema is pinned by `uv run python -m pytest modules/shared/tests/contract_status_schema.py -v` → 3 passed (commit `16de58b`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals and scope | [PRD.md](../../PRD.md) |
| FRD | Functional requirements specification | [FRD.md](FRD.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
