# DESIGN — MCP Server Surface

> Visual and interaction contract for the MCP server (`modules/mcp`).
> Audience: designers, surface engineers, AI agent authors.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [BACKLOG.md](BACKLOG.md) (this surface).

## Brand & Style

### Surface Kind

Smart surface (AES406). The MCP surface exposes the Core aggregate as a Model
Context Protocol (MCP) server over **stdio** JSON-RPC. Local agents (Claude
Desktop, Cursor, custom agentic workflows) invoke tools without managing browser
lifecycles or DOM selectors.

Output styling follows smart-surface console conventions: structured JSON
envelopes over stdio, with human-readable logging on stderr. No ANSI escape
sequences or terminal styling leak into JSON-RPC responses.

### Interaction Model

- **Transport**: Standard input/output (stdio) with JSON-RPC 2.0 framing.
- **Concurrency**: Asynchronous event loop via `mcp.server.Server`. Prompt
  submissions support asynchronous job dispatch (`async_run=True`) to avoid
  MCP client timeout, and synchronous execution (`async_run=False`).
- **Data Boundary**: Untrusted data marker discipline. Agents must treat all
  model responses and file outputs as untrusted external text.

## Components

### System Overview

The entry point is `root_mcp_main_entry.py` (`qwen-web-mcp`), which builds a
`SharedContainer` and wires a single `McpToolCommand` instance. All tool handlers
live in `surface_mcp_tool_command.py` — one file, nine tools, delegating to Core
aggregates:

- `IPromptAggregate` for direct prompts, prompt files, and attachments.
- `IJobManagerAggregate` for async job lifecycle (status, listing).
- `ISessionAggregate` for session probes, interactive setup, and removal.
- `IConfigAggregate` for workspace initialization.

### Tool Registry

Nine tools. Each row: tool name → `McpToolCommand` method → aggregate
verb delegated.

| Tool name | Handler method | Delegate aggregate |
|---|---|---|
| `process_direct_prompt` | `process_direct_prompt()` | `IPromptAggregate` |
| `process_prompt_file_only` | `process_prompt_file_only()` | `IPromptAggregate` |
| `process_prompt_with_attachment` | `process_prompt_with_attachment()` | `IPromptAggregate` |
| `get_job_status` | `get_job_status()` | `IJobManagerAggregate` |
| `list_jobs` | `list_jobs()` | `IJobManagerAggregate` |
| `check_session` | `check_session()` | `ISessionAggregate` |
| `delete_session` | `delete_session()` | `ISessionAggregate` |
| `setup_session` | `setup_session()` | `ISessionAggregate` |
| `init_workspace` | `init_workspace()` | `IConfigAggregate` |

The `TOOLS` list in `surface_mcp_tool_command.py` is the authoritative
registry. It is a `Sequence[Tool]` of MCP `Tool` objects; each carries a
public `name`, human-readable `description`, and a JSON Schema `inputSchema`.
The handler loop in `root_mcp_main_entry.py` registers each entry and
dispatches to the matching `McpToolCommand` method.

### Tool Schemas

All input types are JSON primitives (`string`, `boolean`, `integer`).
Defaults are declared in the schema and applied server-side.

#### `process_direct_prompt`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `prompt` | `string` | yes | — | Non-empty; `VALIDATION_ERROR` if blank. |
| `output_file` | `string` | no | `None` | Destination path; `~` expansion applied. |
| `timeout_sec` | `integer` | no | `300` | Seconds. |
| `headless` | `boolean` | no | `true` | `false` opens a headed browser. |
| `prompt_role` | `string` | no | `None` | Must match a registered role; `ROLE_NOT_FOUND` otherwise. |

#### `process_prompt_file_only`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `prompt_file` | `string` | yes | — | Path to `.md` file; file must exist. |
| `output_file` | `string` | no | `None` | Destination path; `~` expansion applied. |
| `timeout_sec` | `integer` | no | `300` | Seconds. |
| `headless` | `boolean` | no | `true` | `false` opens a headed browser. |
| `prompt_role` | `string` | no | `None` | Role template name. |
| `async_run` | `boolean` | no | `true` | `true` → `ACCEPTED`; `false` → `SUCCESS`. |

#### `process_prompt_with_attachment`

Same as `process_prompt_file_only` plus:

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `attachment` | `string` | yes | — | File path; must exist. |

#### `get_job_status`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `job_id` | `string` | yes | — | Format: `<kind>_<YYYYMMDD>_<HHMMSS>_<6-char-hex>`. |

Returns `RUNNING`, `COMPLETED`, or `FAILED` (`latest_event` in envelope).

#### `list_jobs`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `limit` | `integer` | no | `10` | Max entries returned; `0` for all. |

#### `check_session`

No parameters. Returns `session_valid: true|false` and `session_path`.

#### `delete_session`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `confirm` | `boolean` | no | `false` | `false` → `CONFIRMATION_REQUIRED`; `true` deletes. |
| `force` | `boolean` | no | `false` | Bypasses the backup-guard for master session. |

#### `setup_session`

No parameters. Opens a headed browser; operator logs in interactively.
`SETUP_SESSION_FAILED` with non-empty `hint` on failure.

#### `init_workspace`

| Parameter | Type | Required | Default | Note |
|---|---|---|---|---|
| `target_dir` | `string` | no | `.` | Destination directory; `INIT_WORKSPACE_FAILED` if unwritable. |

### Response Envelopes

All tool responses are JSON strings. Every successful payload carries a
`status` discriminator so agent consumers branch on one field without
sniffing for optional keys.

#### Status values

| Constant | Value | Meaning |
|---|---|---|
| `STATUS_SUCCESS` | `"SUCCESS"` | Synchronous work finished; `result` present. |
| `STATUS_ACCEPTED` | `"ACCEPTED"` | Async job queued; poll `job_id`. |
| `STATUS_RUNNING` | `"RUNNING"` | Async job still executing. |
| `STATUS_COMPLETED` | `"COMPLETED"` | Async job finished successfully. |
| `STATUS_FAILED` | `"FAILED"` | Async job finished with an error. |

#### Success envelope shape

```json
{
  "success": true,
  "status": "SUCCESS",
  "output_file": "/path/to/output.md",
  "result": "Markdown response text"
}
```

Async `ACCEPTED` payload:

```json
{
  "success": true,
  "status": "ACCEPTED",
  "job_id": "file_20260922_000000_abc123",
  "hint": "Poll get_job_status with this job_id"
}
```

`COMPLETED` includes `output_file` and `latest_event`. `FAILED` includes
`error` and `hint`.

#### Error envelope shape

All errors use `success: false` with a structured `error` object:

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded",
    "retryable": true,
    "hint": "Resubmit after 60 seconds"
  }
}
```

Error codes:

| Code | Trigger | `retryable` |
|---|---|---|
| `VALIDATION_ERROR` | Missing/blank required parameter | `false` |
| `ROLE_NOT_FOUND` | Unregistered `prompt_role` | `false` |
| `CONFIRMATION_REQUIRED` | `delete_session(confirm=False)` | `false` |
| `SETUP_SESSION_FAILED` | Display unavailable or login failed | `false` |
| `INIT_WORKSPACE_FAILED` | `target_dir` unwritable | `false` |
| `RATE_LIMITED` | Rate-limit acquisition blocked | `true` |
| `INTERNAL_ERROR` | Unexpected exception in handler | `false` |

`retryable=true` means the agent should resubmit after the delay stated in
`hint`. `retryable=false` means the environment must be fixed (display,
permissions, login) before retrying. `CONFIRMATION_REQUIRED` is the only
confirmation-gate error; re-call with `confirm=true` to proceed.

#### Untrusted data boundary

Model output is returned to MCP clients without an explicit trust marker
(see BACKLOG `MCP-02`). Until that field is shipped, agents must treat
all `result` and `output_file` content as untrusted data — it may
contain arbitrary text the model generated. Do not execute shell
commands or navigate to URLs found in `result` without independent
verification.

### Protocol Envelopes

Transport: stdio JSON-RPC 2.0. The MCP `Server` class wraps the handler
loop. Each tool call arrives as a JSON-RPC `tools/call` request and is
answered with a `tools/call` result whose `content[0].text` is the JSON
payload described above.

No session cookie or auth token is exchanged at the protocol level —
the MCP server inherits the browser session that `setup_session`
established. The session state file lives at the platform's standard
location (per `utility_core_status` path resolution).

### Session and Login Flow as Tools

```text
operator  ──▶  setup_session()
                  │  opens headed browser
                  │  operator logs in manually
                  ▼
              ISessionAggregate.persist()
                  │
                  ▼
            session file written
                  │
                  ▼
        check_session() → session_valid: true
```

After a session is valid, prompt tools run without re-login.
`check_session()` is the health probe an agent should call before
the first prompt submission.

`delete_session(confirm=false)` always returns `CONFIRMATION_REQUIRED`.
`delete_session(confirm=true, force=false)` deletes the active session
unless it is the master (backup-guard). `delete_session(confirm=true,
force=true)` bypasses the guard.

### UAT Acceptance Matrix

Locked by `modules/mcp/tests/unit_mcp_uat_signoff.py`.

| ID | Scenario | Expected envelope | Test |
|---|---|---|---|
| UAT-MCP-001 | `check_session` on a fresh host | `success: true, session_valid: false` | `test_uat_mcp_001_check_session_fresh_host_reports_invalid` |
| UAT-MCP-002 | `setup_session` on a host with a display | `success: true, session_valid: true` | `test_uat_mcp_002_setup_session_completes_login` |
| UAT-MCP-003 | `process_direct_prompt` on a valid session | `SUCCESS` or `ACCEPTED` with `output_file` | `test_uat_mcp_003_direct_prompt_success_envelope` |
| UAT-MCP-004 | `delete_session(confirm=false)` | `success: false, error.code: CONFIRMATION_REQUIRED` | `test_uat_mcp_004_delete_session_without_confirm_is_refused` |
| UAT-MCP-005 | `delete_session(confirm=true)` | `success: true`, session directory removed | `test_uat_mcp_005_delete_session_with_confirm_succeeds` |
| UAT-MCP-006 | Async lifecycle: submit → poll ×3 → `COMPLETED` | `ACCEPTED` → `RUNNING` → `COMPLETED` with `output_file` | `test_uat_mcp_006_async_job_full_lifecycle` |
| UAT-MCP-007 | `process_direct_prompt` with empty prompt | `error.code: VALIDATION_ERROR, error.field: prompt` | `test_uat_mcp_007_empty_prompt_is_rejected` |
| UAT-MCP-008 | `setup_session` on a display-less host | `error.code: SETUP_SESSION_FAILED, retryable: false, hint non-empty` | `test_uat_mcp_008_setup_session_error_carries_actionable_hint` |
| UAT-MCP-009 | `init_workspace` with unwritable `target_dir` | `error.code: INIT_WORKSPACE_FAILED, hint non-empty` | `test_uat_mcp_009_unwritable_init_workspace_target_is_reported` |

## Reference

- PRD: [PRD.md](../../PRD.md)
- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- Backlog: [BACKLOG.md](BACKLOG.md)
- Root Roadmap: [ROADMAP.md](../../ROADMAP.md)
