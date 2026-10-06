# DESIGN — MCP Server Surface

> Surface contract for the MCP server (`modules/mcp`): functional requirements
> in this document (former FRD.md content) plus a pointer to the feature
> [BACKLOG.md](BACKLOG.md). The MCP surface is covered by this DESIGN.md.

## Brand & Style

Smart-surface console output: plain ANSI text, no color unless `--json` is
off. Component styling is driven by the existing text rendering helpers in
`modules/cli/src/surface_cli_*`; the MCP surface reuses them for tool output
rendering.

## Components

- **Tool surface** (`surface_mcp_tool_command`): registers and dispatches the
  MCP tool registry; maps tool calls onto aggregate requests.
- **Session surface** (`surface_mcp_session_command`): exposes session
  lifecycle tools against the session aggregate.
- **Job surface**: async tool plumbing over the jobs aggregate.

### System Overview

The MCP surface (`modules/mcp`) exposes the Core aggregate as a Model Context Protocol (MCP) server over stdio. It allows local AI agents such as Claude Desktop, Cursor, or custom agentic workflows to invoke qwen-web capabilities as standardized tools without managing browser lifecycles or DOM selectors.

### Functional Requirements

#### FR-MCP-001: Declarative Tool Registration and Specification

- **Description**: Registers all MCP capabilities as tools from the `TOOLS` registry.
- **Input**: a specification entry carrying the public tool name, core method name, documentation, and parameter metadata.
- **Output**: one generated async MCP handler per specification entry.
- **Business Rules**:
  - The tool table is the single source of truth for MCP registration.
  - The registry maps one-to-one with exposed capabilities: `process_direct_prompt`, `process_prompt_file_only`, `process_prompt_with_attachment`, `get_job_status`, `list_jobs`, `check_session`, `delete_session`, `setup_session`, and `init` (or `init_workspace`).
  - Asynchronous background jobs delegate to the Core job-manager aggregate backed by the job-storage protocol.
  - Each parameter declares a supported type and default value.
- **Edge Cases**: a tool whose backing Core dependency is missing still registers; the call returns a structured error rather than failing server startup.
- **Error Handling**: missing dependencies or execution errors return structured JSON error payloads containing `code`, `message`, and `hint`.

#### FR-MCP-002: Structured Response Envelopes & Agent-Friendly Payloads

- **Description**: All MCP tools return machine-readable, structured JSON strings.
- **Input**: the underlying tool execution result: status, payload fields, and error state.
- **Output**: a success payload `{"success": true, "status": "...", ...}` or an error payload `{"success": false, "error": {"code": "...", "message": "...", "hint": "...", "retryable": boolean}}`.
- **Business Rules**:
  - Every successful payload carries `success: true` **and** a `status` discriminator, so a consumer branching on `status` never meets a missing key.
  - Every successful payload carries either `result` (work finished) or `job_id` (work queued), so a consumer always knows where the answer comes from.
  - Unknown `status` values from the Core pass through verbatim and are never coerced.
- **Edge Cases**: `hint` is always a non-empty string; the surface fills an actionable default when the Core provides none.
- **Error Handling**: every error payload is a single JSON string; a consumer never receives a bare exception object or a non-JSON error.

| `status` | Meaning | Also present |
|----------|---------|--------------|
| `SUCCESS` | Synchronous work completed. | `result`, optional `output_path`, `run_id` |
| `ACCEPTED` | Async job queued (`async_run=True`, the default). | `job_id`, `latest_event`, `created_at` |
| `RUNNING` | Polled job is still executing. | `job_id`, `latest_event` |
| `COMPLETED` | Polled job finished successfully. | `job_id`, `result_preview`, `duration_sec` |
| `FAILED` | Polled job failed. | `job_id`, `error` |
| `SESSION_VALID` / `SESSION_INVALID` | Session check verdict. | `session_valid` |
| `CONFIRMATION_REQUIRED` | Destructive action refused without its confirm flag. | `error.hint` |
| `VALIDATION_ERROR` | Input rejected before the Core aggregate was invoked. | `error.field` |
| `SETUP_SESSION_FAILED` | Manual login could not complete. | `error.hint`, `retryable=false` |
| `INIT_WORKSPACE_FAILED` | Target directory is unwritable. | `error.hint` |
| `RATE_LIMITED` | Dispatch throttle tripped. | `error.retry_after_sec`, `retryable=true` |

#### FR-MCP-003: Session Management Tools

- **Description**: Exposes session lifecycle as three tools: `check_session`, `delete_session`, and `setup_session`.
- **Input**: `delete_session(confirm=False, force=False)`; `check_session()` and `setup_session()` take none; saved session storage.
- **Output**: `{"success": true, "session_valid": boolean}` for the check; deletion or setup envelopes for the rest.
- **Business Rules**:
  - `check_session` queries saved session validity and returns the boolean verdict.
  - `delete_session` deletes saved session tokens only when `confirm=True` is explicitly passed.
  - `setup_session` delegates to the Core setup aggregate to launch a headed browser for manual user authentication.
- **Edge Cases**: deleting on a host with no saved session is a successful no-op, not an error.
- **Error Handling**: a deletion without confirmation returns `CONFIRMATION_REQUIRED`; a setup failure returns `SETUP_SESSION_FAILED` with an actionable hint.

#### FR-MCP-004: Asynchronous Execution via the Job Manager Aggregate

- **Description**: The two file-based prompt tools run long prompts outside the MCP request/response window through the Core job-manager aggregate. The surface owns no worker pool, no job storage, and no retry logic.
- **Input**: `async_run: bool` on `process_prompt_file_only` and `process_prompt_with_attachment` (default `True`); a `job_id` for polling.
- **Output**: an `ACCEPTED` envelope carrying `job_id`; poll results come from `get_job_status` as `RUNNING`, `COMPLETED`, or `FAILED`.
- **Business Rules**:
  - `async_run=True` (default) submits to the job aggregate and returns immediately with `job_id`; `async_run=False` runs the aggregate synchronously and returns the final `COMPLETED`/`FAILED` envelope inline.
  - Job lifecycle is owned by the aggregate: the surface never mutates job state, only reads it through `get_job_status`.
  - `get_job_status` on a queued job returns `RUNNING` until `COMPLETED` or `FAILED`; the surface adds no timeout of its own.
  - `list_jobs` returns the most recent job records in submission order, bounded by the caller's `limit` (default 10).
  - Throttling: submission is always fast. The submit path performs only the circuit-breaker check and returns a `job_id` in bounded time, never sleeping on the tool-caller thread. The rate limit is applied at worker dispatch, where the worker blocks until a per-minute slot frees before browser work starts.
- **Edge Cases**: a burst of submits is throttled by deferred execution rather than a stalled tool call, so submit-acknowledged (`ACCEPTED`) and dispatch-throttled (worker waits before `RUNNING`) are distinct states. The `job_id` arrives immediately either way; only the start of browser work moves.
- **Error Handling**: an unknown `job_id` returns `JOB_NOT_FOUND`; a rejected submission returns a circuit-open-style envelope, and a throttled path raises a rate-limit envelope carrying `retryable: true` and a `retry_after_sec` hint.

### API Contract

#### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `IJobManagerAggregate.execute(request: JobRequest) -> JobResponse` | job type, payload, `async_run`, model, output path | job response (status, `job_id`, output on completion) | circuit-open, capacity rejection, storage failure | job accepted, running, completed, failed | Submits and polls prompt jobs through the storage-backed aggregate. |
| `ISessionAggregate.execute(request: SessionRequest) -> SessionResponse` | action (check, delete, setup), session path | session response (`session_valid`, confirmation outcome) | `CONFIRMATION_REQUIRED`, `SETUP_SESSION_FAILED` | login complete | Session check, deletion, and manual setup. |
| `IPromptAggregate.execute(request: PromptRequest) -> PromptResponse` | prompt text or file, attachment, model, output | prompt response (status, output path) | validation or processing failure | prompt lifecycle | Direct, file-only, and attachment prompt execution. |
| `IWorkspaceProtocol.init_workspace(target_dir) -> WorkspaceReport` | target directory | created workspace paths | unwritable target | — | Workspace scaffolding for the `init_workspace` tool. |

#### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `process_direct_prompt(prompt, timeout_sec=120, headless=True, output_file=None)` | raw prompt text, timeout, headless flag, output path | JSON envelope string | `VALIDATION_ERROR` on an empty prompt | prompt lifecycle | Processes a raw text prompt; `output_file` mirrors the CLI's `prompt-direct -o FILE`. |
| `process_prompt_file_only(input_file, output_file=None, headless=True, async_run=True)` | prompt file path, output path, headless and async flags | JSON envelope string | missing file returns `VALIDATION_ERROR` | job accepted when async | Processes one Markdown file. |
| `process_prompt_with_attachment(prompt_file, attachment_file, output_file=None, headless=True, async_run=True)` | prompt file, attachment path, output path, headless and async flags | JSON envelope string | missing file or attachment returns `VALIDATION_ERROR` | job accepted when async | Processes a Markdown file with a document attachment. |
| `get_job_status(job_id)` | job id | JSON envelope (`RUNNING`/`COMPLETED`/`FAILED`) | unknown id returns `JOB_NOT_FOUND` | — | Queries state and progress of an asynchronous background job. |
| `list_jobs(limit=10)` | result limit | JSON envelope of recent job records | — | — | Lists recently recorded background jobs, newest first. |
| `check_session()` | — | JSON envelope (`session_valid`) | — | — | Checks validity of saved Chromium session tokens. |
| `delete_session(confirm=False, force=False)` | confirmation flags | JSON envelope | `CONFIRMATION_REQUIRED` without `confirm=True` | — | Deletes saved browser session tokens. |
| `setup_session()` | — | JSON envelope | `SETUP_SESSION_FAILED` (display, auth) | login complete | Launches a visible browser for manual login setup through the Core setup aggregate. |
| `init_workspace(target_dir=".")` | target directory | JSON envelope | `INIT_WORKSPACE_FAILED` (unwritable target) | — | Initializes the workspace directory structure and the skill guide. |

### Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Core aggregate (prompt, jobs, session, setup, config, update) | outbound | All tool execution is delegated; the MCP surface owns presentation and the tool registry only. | A Core error envelope is re-emitted as a structured MCP error payload. |
| AI-agent consumers (Claude Desktop, Cursor, custom workflows) | inbound | Tools are invoked over stdio; consumers branch on `status` and honor `retryable`. | Malformed input is rejected at the tool boundary with `VALIDATION_ERROR`. |
| XDG job storage | read/write | Job records and status files persist across calls. | A storage failure surfaces as a structured job error envelope. |
| Host filesystem | read/write | Prompt files, attachments, and output paths resolve relative to the caller's working directory. | An unwritable or missing path is reported with a `hint`; relative and `~` paths are expanded before execution. |

### Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Predictability and safety | Destructive actions (session deletion) require an explicit confirmation flag | `delete_session` without `confirm=True` returns `CONFIRMATION_REQUIRED` and deletes nothing. |
| Path resolution | Relative paths and `~` are expanded and resolved before execution | Path-resolution tests for relative, absolute, and home-relative inputs. |
| Envelope completeness | 100% of responses are a single JSON string carrying `success` or `error` | Envelope shape tests across every tool. |
| Non-blocking tool calls | No tool call sleeps on the caller thread waiting for a rate-limit slot | Worker-dispatch throttle test under a burst of submits. |
| Bounded submission | Job submit returns `ACCEPTED` in bounded time; rate limiting applies at worker dispatch | Submit-latency measurement under saturation. |

### Test Scenarios

- `check_session` on a fresh host reports `session_valid=false` without raising.
- `delete_session` refuses without `confirm=True` and deletes with it.
- A full async job lifecycle: submit, poll three times, reach `COMPLETED` with an `output_file` present.
- `process_direct_prompt` with an empty prompt returns `VALIDATION_ERROR` and the aggregate is never invoked.
- `setup_session` on a display-less host returns `SETUP_SESSION_FAILED` with an actionable hint.
- `init_workspace` on an unwritable target returns `INIT_WORKSPACE_FAILED` with a hint.
- A burst of submits returns `job_id` immediately while the worker waits for its rate-limit slot.

**UAT sign-off (issue #286).** The acceptance scenarios for the AI-agent consumer persona. Every scenario below is locked by a test carrying the `uat` marker; the evidence rows themselves live in the Backlog section of this document.

| ID | Scenario | Expected | Locked by |
|---|---|---|---|
| UAT-MCP-001 | `check_session` on a fresh host | `{"success": true, "session_valid": false}` | `test_uat_mcp_001_check_session_fresh_host_reports_invalid` |
| UAT-MCP-002 | `setup_session` on a host with a display | Headed browser opens, the operator logs in, `{"success": true, "session_valid": true}` | `test_uat_mcp_002_setup_session_completes_login` |
| UAT-MCP-003 | `process_direct_prompt` on a valid session | `SUCCESS` (or `ACCEPTED` with `async_run=True`) and an `output_file` on completion | `test_uat_mcp_003_direct_prompt_success_envelope` |
| UAT-MCP-004 | `delete_session` with `confirm=False` | `success=false`, `error.code=CONFIRMATION_REQUIRED`, session NOT deleted | `test_uat_mcp_004_delete_session_without_confirm_is_refused` |
| UAT-MCP-005 | `delete_session` with `confirm=True` | `success=true`, session directory removed | `test_uat_mcp_005_delete_session_with_confirm_succeeds` |
| UAT-MCP-006 | Full async lifecycle: submit, poll x3, `COMPLETED` | `ACCEPTED` to `RUNNING` to `COMPLETED` with `output_file` on the completed envelope | `test_uat_mcp_006_async_job_full_lifecycle` |
| UAT-MCP-007 | `process_direct_prompt` with an empty prompt | `error.code=VALIDATION_ERROR`, `error.field=prompt`, aggregate never invoked | `test_uat_mcp_007_empty_prompt_is_rejected` |
| UAT-MCP-008 | `setup_session` on a display-less host | `error.code=SETUP_SESSION_FAILED`, `retryable=false`, non-empty `hint` | `test_uat_mcp_008_setup_session_error_carries_actionable_hint` |
| UAT-MCP-009 | `init_workspace` with an unwritable `target_dir` | `error.code=INIT_WORKSPACE_FAILED`, non-empty `hint` | `test_uat_mcp_009_unwritable_init_workspace_target_is_reported` |

**Error-recovery contract the agent relies on**: `retryable=true` means resubmit after the hint's delay; `retryable=false` means fix the environment (display, permissions, login) before retrying. `CONFIRMATION_REQUIRED` is the only confirmation error, and the agent re-issues the call with `confirm=true` rather than aborting the session flow.

### Assumptions & Constraints

- One persistent Chromium session profile per host; `setup_session` is interactive and headed.
- The surface owns no worker pool, job storage, or retry logic; the job aggregate owns lifecycle.
- Consumers are assumed to branch on the `status` discriminator and honor `retryable`.
- Tool registration is driven by the registry table, not by a code change per tool.
- Relative and home-relative paths are expanded before execution, so a caller's working directory defines resolution.

### Glossary

- **MCP**: Model Context Protocol, the stdio tool protocol this surface implements.
- **Envelope**: the single JSON string every tool returns, carrying either a success payload or a structured error payload.
- **Job**: a long-running background prompt execution managed by the Core job-manager aggregate.
- **`job_id`**: the identifier returned on `ACCEPTED` and used to poll through `get_job_status`.
- **Submit-acknowledged vs dispatch-throttled**: two distinct states — the `job_id` arrives immediately in both, but only the start of browser work moves under throttling.
- **UAT sign-off**: the acceptance criteria an AI-agent consumer validates against; the evidence rows live in the Backlog section of this document.

### Backlog

Feature status, evidence, and blocked work for this surface live in [BACKLOG.md](BACKLOG.md).

## Reference

- **Product**: [PRD.md](../../PRD.md) owns product scope.
- **State**: [BACKLOG.md](BACKLOG.md) owns feature status.
- **Architecture**: Layer boundaries in [ARCHITECTURE.md](../../ARCHITECTURE.md).
