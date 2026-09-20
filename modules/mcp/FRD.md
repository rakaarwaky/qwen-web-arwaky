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
  - The `TOOLS` registry maps one-to-one with exposed capabilities: `process_direct_prompt`, `process_prompt_file_only`, `process_prompt_with_attachment`, `check_session`, `delete_session`, `setup_session`, and `init_workspace`.
  - Each parameter declares a supported type and default value.
- **Error Handling**: Missing dependencies or execution errors return structured JSON error payloads containing `code`, `message`, and `hint`.

### FR-002: Structured Response Envelopes & Agent-Friendly Payloads

- **Description**: All MCP tools return machine-readable, structured JSON strings.
- **Success Payload**: `{"success": true, "status": "SUCCESS", "result": "...", "output_path": "...", "run_id": "..."}`.
- **Error Payload**: `{"success": false, "error": {"code": "...", "message": "...", "hint": "...", "retryable": boolean}}`.

### FR-003: Session Management Tools

- **`check_session`**: Queries saved session validity and returns `{ "success": true, "session_valid": boolean }`.
- **`delete_session`**: Deletes saved session tokens when `confirm=True` is explicitly passed.
- **`setup_session`**: Delegates to `ISetupAggregate` to launch a headed browser for manual user authentication.

---

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `process_direct_prompt` | `prompt`, `timeout_sec=120`, `headless=True` | `JSON str` | Processes a raw text prompt. |
| `process_prompt_file_only` | `input_file`, `output_file=None`, `headless=True` | `JSON str` | Processes one Markdown file. |
| `process_prompt_with_attachment` | `prompt_file`, `attachment_file`, `output_file=None`, `headless=True` | `JSON str` | Processes a Markdown file with a document attachment. |
| `check_session` | None | `JSON str` | Checks validity of saved Chromium session tokens. |
| `delete_session` | `confirm=False` | `JSON str` | Deletes saved browser session tokens. Requires `confirm=True`. |
| `setup_session` | None | `JSON str` | Launches visible browser for manual login setup via `ISetupAggregate`. |
| `init_workspace` | `target_dir="."` | `JSON str` | Initializes workspace directory structure and SKILL.md guide. |

---

## Non-functional Requirements

- **Predictability & Safety**: Destructive actions (session deletion) require explicit confirmation flags.
- **Path Resolution**: Relative paths and user paths (`~`) are automatically expanded and resolved before execution.
