# BACKLOG — MCP Server Surface

Feature prefix: `MCP-`. Last Updated: 2026-10-25.

DESIGN: [DESIGN.md](DESIGN.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).

## Progress Overview

The MCP surface is Done. `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` → 75 passed (2026-10-25, commit `9685d84`); the shipped server exports 9 tools with structured JSON-RPC response envelopes. No row is in progress or blocked; every entry is Done.

## Backlog Status

### DS-MCP-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/mcp/tests/unit_mcp_hardening.py -v` covers stdio JSON-RPC framing and concurrency modes (`async_run=true` → `ACCEPTED`, `false` → `SUCCESS`). Verified 2026-10-22; trust marker discipline documented. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-MCP-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` → 75 passed (2026-10-25, commit `9685d84`). Nine tools registered via `TOOLS` list in `surface_mcp_tool_command.py`, each delegating to its Core aggregate (`IPromptAggregate`, `IJobManagerAggregate`, `ISessionAggregate`, `IConfigAggregate`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-MCP-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | When `jobs is None`, `get_job_status`/`list_jobs` return `SERVICE_UNAVAILABLE`; prompt tools fall through to `IPromptAggregate`; `shutdown()` calls `JobRequest(verb="shutdown")` on server exit. Documented in DESIGN.md §Job Manager dependency (issue #315). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-MCP-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Status discriminators `SUCCESS`/`ACCEPTED`/`RUNNING`/`COMPLETED`/`FAILED` shipped in every envelope; pinned by `unit_mcp_response_envelope.py` trust-marker tests and UAT-MCP-010. Verified `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` → 75 passed (commit `9685d84`); `uv run ruff check modules/mcp/` clean. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-MCP-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Error codes pinned: `VALIDATION_ERROR`, `ROLE_NOT_FOUND`, `CONFIRMATION_REQUIRED`, `SETUP_SESSION_FAILED`, `INIT_WORKSPACE_FAILED`, `RATE_LIMITED`, `QUEUE_FULL`, `INTERNAL_ERROR`. Documented in DESIGN.md §Error Codes (issue #343, #383). Verified 2026-10-22. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-MCP-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Every envelope exposing model output carries `result_trust: "untrusted_model_output"` + `security_notice`; `list_jobs` payload and each item carry `security_notice`; result-bearing `TOOLS` descriptions name `result_trust`. Documented in DESIGN.md §Untrusted data boundary. Verified 2026-10-22. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals and scope | [PRD.md](../../PRD.md) |
| DESIGN | Surface specification | [DESIGN.md](DESIGN.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
