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

---

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `process_direct_prompt` | `prompt`, `timeout_sec=120`, `headless=True`, `output_file=None` | `JSON str` | Processes a raw text prompt. `output_file` mirrors the CLI's `prompt-direct -o FILE`. |
| `process_prompt_file_only` | `input_file`, `output_file=None`, `headless=True` | `JSON str` | Processes one Markdown file. |
| `process_prompt_with_attachment` | `prompt_file`, `attachment_file`, `output_file=None`, `headless=True` | `JSON str` | Processes a Markdown file with a document attachment. |
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
