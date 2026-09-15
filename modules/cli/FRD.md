# CLI Functional Requirements Document

## System Overview

The CLI surface (`modules/cli`) translates command-line arguments and interactive TTY inputs into `AppConfig` objects and delegates execution to the Core aggregate. It remains a **Smart Surface**: presentation, argument validation, dispatch, and lifecycle-boundary concerns belong here; business processing semantics remain in `modules/core`.

The CLI root (`modules/root_cli_main_entry.py`) owns the CLI lifecycle: parse arguments, build `AppConfig`, and dispatch to the Core aggregate. The MCP root is a separate runtime and does not enter the CLI dispatch path.

## Functional Requirements

### FR-001: Subcommand Argument Parsing & Config Building

The root parser reads `sys.argv` using a subcommand-based interface (`init`, `login`, `doctor`, `prompt-direct`, `prompt-only`, `prompt-with-attachment`, `mcp`).

| Subcommand | Signal | Result | Validation |
|---|---|---|---|
| `doctor` | `qwen-web-arwaky doctor [--json]` | System health diagnostic | Checks Python, Playwright, workspace, session, permissions. |
| `login` | `qwen-web-arwaky login [--headless]` | `mode="login"` | Forces headed browser for manual authentication unless overridden. |
| `init` | `qwen-web-arwaky init [--dir]` | Workspace initialization | Creates XDG storage directories and root `.qwen-web` symlinks. |
| `prompt-direct` | `qwen-web-arwaky prompt-direct -t "..." [--json]` | Inline text prompt | Direct text string is injected directly. |
| `prompt-only` | `qwen-web-arwaky prompt-only -i FILE [--json]` | `mode="single"` | Prompt file must exist on disk. |
| `prompt-with-attachment` | `qwen-web-arwaky prompt-with-attachment -i FILE -a FILE [--json]` | Attachment prompt | Prompt file and attachment file must exist. |
| `mcp` | `qwen-web-arwaky mcp` | MCP Stdio Server | Hands off execution to MCP stdio server. |

An invalid run input is rejected with a non-success exit code and a clear, actionable diagnostic on `stderr`.

### FR-002: Modern Obsidian Nebula Textual TUI Dashboard

The no-argument TTY fallback launches the **Obsidian Nebula Textual TUI App** (`surface_cli_tui_app.py`).

1. **Dynamic Versioning**: Header displays package version dynamically via `importlib.metadata.version("qwen-web-arwaky")`.
2. **Safe Default Attachment**: If candidate attachment files do not exist on disk, attachment input defaults to an empty string `""` so optional fields never fail validation.
3. **Output Folder Auto-Naming**: If an output path is a directory, a timestamped filename (e.g. `qwen_output_YYYYMMDD_HHMMSS.md`) is automatically resolved.
4. **Destructive Action Safety**: Session reset actions present a modal confirmation screen (`ConfirmModal`) before wiping session tokens.
5. **Non-TTY Rejection**: Running the interactive TUI in non-interactive environments (pipes/cron) prints a helpful, example-driven guidance message pointing to subcommands and `qwen-web-arwaky doctor`.

### FR-003: Manual Login & Session Setup

The login surface accepts an `AppConfig` and delegates session setup to the Core aggregate. It forces headed mode at configuration construction, validates an existing session through the core, and reports success after the core verifies the authenticated chat UI.

### FR-004: System Diagnostic Command (`doctor`)

The `doctor` subcommand verifies environment health across 5 key dimensions:
1. Python runtime version (>= 3.10)
2. Playwright Chromium browser binary existence
3. Local workspace `.qwen-web/` initialization
4. Session authentication token directory (`qwen_session/`)
5. Output directory write permissions

Supports optional `--json` flag for machine-readable JSON output by AI agents and automated scripts.

---

## API Contract

| Operation | Input | Output | Production caller |
|---|---|---|---|
| `_parse_args` | argv tokens | `argparse.Namespace` | `modules/root_cli_main_entry.py` |
| `_build_config` | parsed namespace | validated `AppConfig` | `modules/root_cli_main_entry.py` |
| `handle` (run) | args, core | response envelope | `modules/cli/src/surface_cli_run_command.py` |
| `handle` (login) | args, core, cfg | response envelope | `modules/cli/src/surface_cli_login_command.py` |
| `handle` (init) | args, core | response envelope | `modules/cli/src/surface_cli_init_command.py` |
| `run_doctor` | json_output flag | process exit code | `modules/cli/src/surface_cli_doctor_command.py` |
| `InteractiveController.run` | optional config | response envelope | `modules/root_cli_main_entry.py` |

---

## Non-functional Requirements

- **Actionable Error Messages**: Errors specify *what happened*, *why it happened*, and *how to fix it*.
- **Machine-Readable Output**: Subcommands support `--json` for AI agent consumption.
- **Data Safety**: Destructive actions require explicit modal confirmation.
