# DESIGN — MCP Server Surface

## Design Overview

A smart surface (AES406) for `qwen-web-mcp`: it exposes the Core aggregate as a Model Context Protocol (MCP) server over stdio JSON-RPC. Local agents invoke tools without managing browser lifecycles or DOM selectors. Output styling follows smart-surface console conventions — structured JSON envelopes over stdio, human-readable logging on stderr — and no ANSI escape sequences or terminal styling leak into JSON-RPC responses.

## Design Requirements

### DS-MCP-001: Interaction Model

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Transport | stdio with JSON-RPC 2.0 framing | `mcp.server.Server` | one transport |
| Concurrency | Async event loop; `async_run=True` for job dispatch | `async_run` | `true` → `ACCEPTED`, `false` → `SUCCESS` |
| Data boundary | Treat all model responses and file outputs as untrusted | `result_trust` | `untrusted_model_output` |

### DS-MCP-002: Tool Registry

Nine tools. Each row: tool name → `McpToolCommand` method → delegate aggregate. The `TOOLS` list in `surface_mcp_tool_command.py` is the authoritative registry.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `process_direct_prompt` | Inline text prompt | `process_direct_prompt()` | `IPromptAggregate` |
| `process_prompt_file_only` | Prompt file only | `process_prompt_file_only()` | `IPromptAggregate` |
| `process_prompt_with_attachment` | Prompt file plus attachment | `process_prompt_with_attachment()` | `IPromptAggregate` |
| `get_job_status` | Poll an async job | `get_job_status()` | `IJobManagerAggregate` |
| `list_jobs` | List job records | `list_jobs()` | `IJobManagerAggregate` |
| `check_session` | Probe the active session | `check_session()` | `ISessionAggregate` |
| `delete_session` | Remove a session | `delete_session()` | `ISessionAggregate` |
| `setup_session` | Interactive login | `setup_session()` | `ISessionAggregate` |
| `init` | Workspace initialization | `init_workspace()` | `IConfigAggregate` |

### DS-MCP-003: Job Manager Dependency

`McpToolCommand` delegates async job lifecycle to the `IJobManagerAggregate` injected through the `jobs` constructor argument.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Missing aggregate | `jobs is None` on job tools | `SERVICE_UNAVAILABLE` | `success: false`, `retryable: false` |
| Sync fallthrough | `jobs is None` on prompt tools | `IPromptAggregate` | synchronous path |
| Shutdown | Server exit releases job resources | `JobRequest(verb="shutdown")` | not exposed as a tool |

### DS-MCP-004: Response Envelopes

All tool responses are JSON strings. Every successful payload carries a `status` discriminator so consumers branch on one field.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `SUCCESS` | Synchronous work finished | `STATUS_SUCCESS` | `result` present |
| `ACCEPTED` | Async job queued | `STATUS_ACCEPTED` | poll `job_id` |
| `RUNNING` | Async job in flight | `STATUS_RUNNING` | `latest_event` |
| `COMPLETED` | Async job finished | `STATUS_COMPLETED` | `output_file` |
| `FAILED` | Async job errored | `STATUS_FAILED` | `error` string |

### DS-MCP-005: Error Codes

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | Missing/blank required parameter | `false` | `retryable` |
| `ROLE_NOT_FOUND` | Unregistered `prompt_role` | `false` | `retryable` |
| `CONFIRMATION_REQUIRED` | `delete_session(confirm=False)` | `false` | `retryable` |
| `SETUP_SESSION_FAILED` | Display unavailable or login failed | `false` | `retryable` |
| `INIT_WORKSPACE_FAILED` | `target_dir` unwritable | `false` | `retryable` |
| `RATE_LIMITED` | Rate-limit acquisition blocked | `true` | `retry_after_sec` |
| `QUEUE_FULL` | Saturated worker pool refused the submission | `true` | `retry_after_sec` + `queue_depth` |
| `INTERNAL_ERROR` | Unexpected exception in handler | `false` | `retryable` |

### DS-MCP-006: Untrusted Data Boundary

Every envelope that exposes model output carries an explicit trust marker (issue #343, BACKLOG `MCP-02`).

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Sync success | `process_direct_prompt`, file, attachment | `result_trust` | `untrusted_model_output` + `security_notice` |
| `get_job_status` | When `result_preview` is present | `result_trust` | `untrusted_model_output` + `security_notice` |
| `list_jobs` | Payload and each item | `security_notice` | always |
| Tool descriptions | Result-bearing `TOOLS` entries | `result_trust` | prose notice naming the field |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](../../PRD.md) |
| Backlog | Task tracking, epics, and implementation status | [BACKLOG.md](BACKLOG.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
