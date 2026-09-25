# MCP Functional Requirements Document

## System Overview

The MCP surface (`modules/mcp`) exposes the Core aggregate as a Model Context Protocol (MCP) server over stdio. It allows local AI agents such as Claude Desktop, Cursor, or custom agentic workflows to invoke qwen-web capabilities as standardized tools without managing browser lifecycles or DOM selectors.

## Functional Requirements

### FR-001: Declarative Tool Registration and Specification

- **Description**: Registers all MCP capabilities as tools from the `TOOLS` registry.
- **Input**: A specification entry containing the public tool name, core method name, documentation, and parameter metadata.
- **Output**: One generated async MCP handler per specification entry.
- **Business Rules**:
  - The tool table is the single source of truth for MCP registration.
  - The `TOOLS` registry maps one-to-one with exposed capabilities: `process_direct_prompt`, `process_prompt_file_only`, `process_prompt_with_attachment`, `get_job_status`, `list_jobs`, `check_session`, `delete_session`, `setup_session`, and `init` (or `init_workspace`).
  - Asynchronous background jobs delegate to `IJobManagerAggregate` (`AgentJobOrchestrator`) backed by `IJobStorageProtocol`.
  - Each parameter declares a supported type and default value.
- **Error Handling**: Missing dependencies or execution errors return structured JSON error payloads containing `code`, `message`, and `hint`.

### FR-002: Structured Response Envelopes & Agent-Friendly Payloads

- **Description**: All MCP tools return machine-readable, structured JSON strings.
- **Success Payload**: `{"success": true, "status": "<STATUS>", ...}`.
- **Error Payload**: `{"success": false, "error": {"code": "...", "message": "...", "hint": "...", "retryable": boolean}}`.
- **Business Rules**:
  - Every successful payload carries `success: true` **and** a `status` discriminator.
    A consumer branching on `status` must never encounter a missing key, whatever
    code path produced the response.
  - Every successful payload carries either `result` (work finished) or `job_id`
    (work queued), so a consumer always knows where the answer will come from.

| `status` | Meaning | Also present |
|----------|---------|--------------|
| `SUCCESS` | Synchronous work completed. | `result`, optional `output_path`, `run_id` |
| `ACCEPTED` | Async job queued (`async_run=True`, the default). | `job_id`, `latest_event`, `created_at` |
| `RUNNING` | Polled job is still executing. | `job_id`, `latest_event` |
| `COMPLETED` | Polled job finished successfully. | `job_id`, `result_preview`, `duration_sec` |
| `FAILED` | Polled job finished with an error. | `job_id`, `error` |

- **Throttling**: when the submission rate limit is reached, tools return the error
  envelope with `code: "RATE_LIMITED"`, `retryable: true`, and a `retry_after_sec`
  hint rather than blocking the tool call until a slot frees up.

### FR-003: Session Management Tools

- **`check_session`**: Queries saved session validity and returns `{ "success": true, "session_valid": boolean }`.
- **`delete_session`**: Deletes saved session tokens when `confirm=True` is explicitly passed.
- **`setup_session`**: Delegates to `ISetupAggregate` to launch a headed browser for manual user authentication.

### FR-004: Asynchronous Execution via the Job Manager Aggregate

- **Description**: The two file-based prompt tools depend on the Core Job Manager aggregate (`IJobManagerAggregate`, implemented by `agent_job_orchestrator.py` → `AgentJobOrchestrator` backed by `IJobStorageProtocol`) to run long prompts outside the MCP request/response window. The surface owns no worker pool, no job storage, and no retry logic.
- **Input**: `async_run: bool` on `process_prompt_file_only` and `process_prompt_with_attachment` (default `True`).
- **Output**: `ACCEPTED` envelope carrying `job_id`; poll results come from `get_job_status` as `RUNNING`, `COMPLETED`, or `FAILED`.
- **Business Rules**:
  - `async_run=True` (default) submits to `IJobManagerAggregate` and returns immediately with `job_id`; `async_run=False` runs the aggregate synchronously and returns a `SUCCESS` envelope with `result`.
  - Polling: submit → receive `job_id` → poll `get_job_status(job_id)` until `completed=true`, then read `result_preview` (or `error` on failure). `list_jobs(limit)` is the recovery path when a `job_id` was lost.
  - When the job manager is not configured, the tools return `SERVICE_UNAVAILABLE` rather than silently degrading to a blocking call.
  - Submission throttling returns `RATE_LIMITED` with `retryable: true` and `retry_after_sec`; the caller retries the submit, never the poll.
  - `JOB_NOT_FOUND` means the `job_id` is unknown or its storage record expired; use `list_jobs` to recover.
- **Error Handling**: `JOB_SUBMIT_FAILED` (retryable), `JOB_NOT_FOUND`, `SERVICE_UNAVAILABLE`, `RATE_LIMITED` — all as structured error envelopes.
- **Acceptance Criteria**:
  - [ ]  `async_run=True` returns `ACCEPTED` with a `job_id` and no `result`.
  - [ ]  `async_run=False` returns `SUCCESS` with a synchronous `result`.
  - [ ]  `get_job_status` on a queued job returns `RUNNING` until `completed=true`, then `COMPLETED` or `FAILED`.

---

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `process_direct_prompt` | `prompt`, `timeout_sec=120`, `headless=True`, `output_file=None` | `JSON str` | Processes a raw text prompt. `output_file` mirrors the CLI's `prompt-direct -o FILE`. |
| `process_prompt_file_only` | `input_file`, `output_file=None`, `headless=True`, `async_run=True` | `JSON str` | Processes one Markdown file. `async_run=True` submits to `IJobManagerAggregate` and returns `ACCEPTED` + `job_id`. |
| `process_prompt_with_attachment` | `prompt_file`, `attachment_file`, `output_file=None`, `headless=True`, `async_run=True` | `JSON str` | Processes a Markdown file with a document attachment. `async_run=True` submits to `IJobManagerAggregate` and returns `ACCEPTED` + `job_id`. |
| `get_job_status` | `job_id` | `JSON str` | Queries state and progress of an asynchronous background job. |
| `list_jobs` | `limit=10` | `JSON str` | Lists recently recorded background jobs sorted newest to oldest. |
| `check_session` | None | `JSON str` | Checks validity of saved Chromium session tokens. |
| `delete_session` | `confirm=False` | `JSON str` | Deletes saved browser session tokens. Requires `confirm=True`. |
| `setup_session` | None | `JSON str` | Launches visible browser for manual login setup via `ISetupAggregate`. |
| `init_workspace` / `init` | `target_dir="."` | `JSON str` | Initializes workspace directory structure and SKILL.md guide. |

---

## Non-functional Requirements

- **Predictability & Safety**: Destructive actions (session deletion) require explicit confirmation flags.
- **Path Resolution**: Relative paths and user paths (`~`) are automatically expanded and resolved before execution.
