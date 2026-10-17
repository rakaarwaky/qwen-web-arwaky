# BACKLOG — MCP Server Surface

Feature prefix: `MCP-`. Last Updated: **2026-10-18**.

State and Health vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).
Surface specification: [DESIGN.md](DESIGN.md).

## Current Condition

- Done: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` passes 26 tests on commit `73aee43` on 2026-10-18. Shipped MCP surface exports 9 tools in `surface_mcp_tool_command.py` with structured JSON-RPC response envelopes.
- In Progress: None.
- Blocked: None.
- Next: `MCP-01`, `MCP-02`, `MCP-03`.

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| Prompt role template integration | Automated | `modules/mcp/tests/integration_prompt_template.py` | `test_mcp_file_only_with_role` | `73aee43` (2 tests pass) |
| MCP tool hardening & parameter validation | Automated | `modules/mcp/tests/unit_mcp_hardening.py` | `test_prompt_path_rejects_files_outside_workspace` | `73aee43` (7 tests pass) |
| Structured response envelope & discriminator contracts | Automated | `modules/mcp/tests/unit_mcp_response_envelope.py` | `test_async_submission_carries_accepted_status` | `73aee43` (11 tests pass) |
| AI agent consumer UAT sign-off criteria | Automated | `modules/mcp/tests/unit_mcp_uat_signoff.py` | `test_uat_mcp_006_async_job_full_lifecycle` | `73aee43` (6 tests pass) |

## Blockers

None.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` passes 26 tests on commit `73aee43`. |
| Scenario evidence | Done | 4 test suites mapped with 26 passing automated tests. |
| Docs | Done | [DESIGN.md](DESIGN.md) specifies tool schemas, response envelopes, session flow, and UAT matrix. |

## Deferred

None.

## Change Log

| Date | Change |
|---|---|
| 2026-10-18 | Rework BACKLOG.md and DESIGN.md per aes-docs templates; record command, counts, and commit evidence |
| 2026-10-05 | Added required BACKLOG template sections |

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| MCP-00 | Standardize MCP server surface tool handlers and JSON-RPC envelopes | P0 | Done | On Track | — | Verified: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` passes 26 tests on commit `73aee43`. Exports 9 MCP tools registered via `TOOLS` list in `surface_mcp_tool_command.py` with typed request schemas and structured JSON response envelopes. | Maintain tool contracts and schema parity with Core aggregates. | 2026-10-18 |
| MCP-01 | Guarantee bounded, non-blocking MCP submissions | P0 | Ready | At Risk | — | Finding [#383](https://github.com/rakaarwaky/qwen-web-arwaky/issues/383) reports that rate-limit acquisition can block a tool call for about 60 seconds. Core queue and worker constraints are owned by `CORE-02`; this row owns the MCP request/response boundary. | Reproduce submit latency under saturation and specify immediate `RATE_LIMITED`/backpressure envelopes with timing acceptance. | 2026-10-18 |
| MCP-02 | Mark model output as untrusted at the agent boundary | P0 | Refinement | At Risk | — | Finding [#343](https://github.com/rakaarwaky/qwen-web-arwaky/issues/343) reports that model output is returned to MCP clients without an explicit trust marker, creating an indirect prompt-injection risk. | Define a backward-compatible trust/provenance field and add contract tests for synchronous and async result envelopes. | 2026-10-18 |
| MCP-03 | Reconcile async-tool documentation and complete consumer UAT | P1 | Refinement | On Track | — | Findings [#315](https://github.com/rakaarwaky/qwen-web-arwaky/issues/315) and [#286](https://github.com/rakaarwaky/qwen-web-arwaky/issues/286) report missing Job Manager dependency documentation and MCP consumer sign-off. [DESIGN.md](DESIGN.md) specifies `IJobManagerAggregate` and async lifecycle; 6 UAT sign-off tests pass in `unit_mcp_uat_signoff.py`. | Close stale reports #315 and #286 after consumer validation sweep against live browser session. | 2026-10-18 |

## Dependencies and Exit Evidence

- MCP surface depends on Root containers (`modules/root_core_container.py`, `modules/root_mcp_main_entry.py`) for orchestrator wiring.
- A row can become Done only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`.
- Verification command: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"`.
