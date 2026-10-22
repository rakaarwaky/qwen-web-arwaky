# BACKLOG — MCP Server Surface

Feature prefix: `MCP-`. Last Updated: **2026-10-18**.

State vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).
Surface specification: [DESIGN.md](DESIGN.md).

## Current Condition

- Done: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` passes 26 tests on commit `73aee43` on 2026-10-18. Shipped MCP surface exports 9 tools in `surface_mcp_tool_command.py` with structured JSON-RPC response envelopes.
- In Progress: None.
- Blocked: None.
- Next: `MCP-03`.

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| Prompt role template integration | Automated | `modules/mcp/tests/integration_prompt_template.py` | `test_mcp_file_only_with_role` | `73aee43` (2 tests pass) |
| MCP tool hardening & parameter validation | Automated | `modules/mcp/tests/unit_mcp_hardening.py` | `test_prompt_path_rejects_files_outside_workspace` | `73aee43` (7 tests pass) |
| Structured response envelope & discriminator contracts | Automated | `modules/mcp/tests/unit_mcp_response_envelope.py` | `test_async_submission_carries_accepted_status` | `73aee43` (11 tests pass) |
| AI agent consumer UAT sign-off criteria | Automated | `modules/mcp/tests/unit_mcp_uat_signoff.py` | `test_uat_mcp_006_async_job_full_lifecycle` | `73aee43` (6 tests pass) |
| Saturated pool keeps its backpressure envelope | Automated | `modules/mcp/tests/unit_mcp_response_envelope.py` | `test_queue_full_submission_keeps_backpressure_fields` | 2026-10-22 |

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

| Date | Change | By |
|---|---|---|
| 2026-10-18 | Rework BACKLOG.md and DESIGN.md per aes-docs templates; record command, counts, and commit evidence | @rakaarwaky |
| 2026-10-05 | Added required BACKLOG template sections | @rakaarwaky |

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---|---|---|---|---|
| MCP-00 | P0 | Done | Standardize MCP server surface tool handlers and JSON-RPC envelopes. Verified: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"` passes 26 tests on commit `73aee43`. Exports 9 MCP tools registered via `TOOLS` list in `surface_mcp_tool_command.py` with typed request schemas and structured JSON response envelopes. | Maintain tool contracts and schema parity with Core aggregates. | 2026-10-18 |
| MCP-01 | P0 | Done | Guarantee bounded, non-blocking MCP submissions. Finding [#383](https://github.com/rakaarwaky/qwen-web-arwaky/issues/383) reports that rate-limit acquisition can block a tool call for about 60 seconds. Core queue and worker constraints are owned by `JOBS-02` in `modules/jobs/BACKLOG.md`; this row owns the MCP request/response boundary. Shipped: `RATE_LIMITED` (retryable, `retry_after_sec`) and `QUEUE_FULL` (retryable, `retry_after_sec` + `queue_depth`) envelopes on both async tools, pinned by `unit_mcp_response_envelope.py::test_queue_full_submission_keeps_backpressure_fields`. Verified 2026-10-22. | Maintain the envelope contract; no open action. | 2026-10-22 |
| MCP-02 | P0 | Done | Mark model output as untrusted at the agent boundary. Finding [#343](https://github.com/rakaarwaky/qwen-web-arwaky/issues/343) reports that model output is returned to MCP clients without an explicit trust marker. Shipped: every envelope exposing model output carries `result_trust: "untrusted_model_output"` + `security_notice` (sync success always; `get_job_status` when `result_preview` is present; `list_jobs` carries `security_notice`), and result-bearing `TOOLS` descriptions name the field. Pinned by `unit_mcp_response_envelope.py` trust-marker tests and UAT-MCP-010; documented in DESIGN.md §Untrusted data boundary. Verified 2026-10-22. Residual: `output_file` file-content trust stays policy prose — file bytes never cross the MCP boundary. | Close issue #343 citing the shipped envelope fields; no code change pending. | 2026-10-22 |
| MCP-03 | P1 | Refinement | Reconcile async-tool documentation and complete consumer UAT. Findings [#315](https://github.com/rakaarwaky/qwen-web-arwaky/issues/315) and [#286](https://github.com/rakaarwaky/qwen-web-arwaky/issues/286) report missing Job Manager dependency documentation and MCP consumer sign-off. [DESIGN.md](DESIGN.md) specifies `IJobManagerAggregate` and async lifecycle; 6 UAT sign-off tests pass in `unit_mcp_uat_signoff.py`. | Close stale reports #315 and #286 after consumer validation sweep against live browser session. | 2026-10-18 |

## Dependencies and Exit Evidence

- MCP surface depends on Root containers (`modules/root_core_container.py`, `modules/root_mcp_main_entry.py`) for orchestrator wiring.
- A row can become Done only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`.
- Verification command: `uv run python -m pytest modules/mcp/tests/ -m "not benchmark and not e2e"`.
