# CLI Functional Requirements Document

## System Overview

The CLI surface (`modules/cli`) translates command-line arguments and interactive TTY inputs into `AppConfig` objects and delegates execution to the Core aggregate. It remains a **Smart Surface**: presentation, argument validation, dispatch, and lifecycle-boundary concerns belong here; business processing semantics remain in `modules/core`.

The CLI root (`modules/root_cli_main_entry.py`) owns the CLI lifecycle: parse arguments, build `AppConfig`, and dispatch to the Core aggregate. The MCP root is a separate runtime and does not enter the CLI dispatch path.

## Functional Requirements

### FR-001: Subcommand Argument Parsing & Config Building

The root parser reads `sys.argv` using a subcommand-based interface (`init`, `login`, `doctor`, `sessions`, `prompt-direct`, `prompt-only`, `prompt-with-attachment`, `update`, `mcp`).

| Subcommand | Signal | Result | Validation |
|---|---|---|---|
| `doctor` | `qwen-web-arwaky doctor [--json] [--smoke]` | System health diagnostic | Checks Python, Playwright, workspace, session, permissions; `--smoke` adds a headless browser round-trip (FR-004). |
| `login` | `qwen-web-arwaky login [--headless]` | `mode="login"` | Forces headed browser for manual authentication unless overridden. |
| `init` | `qwen-web-arwaky init [--dir]` | Workspace initialization | Creates XDG storage directories and root `.qwen-web` symlinks. |
| `prompt-direct` | `qwen-web-arwaky prompt-direct -t "..." [--json]` | Inline text prompt | Direct text string is injected directly. |
| `prompt-only` | `qwen-web-arwaky prompt-only -i FILE [--json]` | `mode="single"` | Prompt file must exist on disk. |
| `prompt-with-attachment` | `qwen-web-arwaky prompt-with-attachment -i FILE -a FILE [--json]` | Attachment prompt | Prompt file and attachment file must exist. |
| `update` | `qwen-web-arwaky update [--check] [--force]` | Self-update management | Discovers latest release, upgrades package, synchronizes Playwright binaries (FR-005). |
| `mcp` | `qwen-web-arwaky mcp` | MCP Stdio Server | Hands off execution to MCP stdio server. |

An invalid run input is rejected with a non-success exit code and a clear, actionable diagnostic on `stderr`.

### FR-002: Modern Obsidian Nebula Textual TUI Dashboard

The no-argument TTY fallback launches the **Obsidian Nebula Textual TUI App** (`surface_cli_tui_app.py`).

1. **Dynamic Versioning**: Header displays package version dynamically via `importlib.metadata.version("qwen-web-arwaky")`.
2. **Safe Default Attachment**: If candidate attachment files do not exist on disk, attachment input defaults to an empty string `""` so optional fields never fail validation.
3. **Output Folder Auto-Naming**: If an output path is a directory, a timestamped filename (e.g. `qwen_output_YYYYMMDD_HHMMSS.md`) is automatically resolved. Existing files are never silently overwritten.
   Invalid, unwritable, or conflicting paths produce an actionable validation error.
4. **Destructive Action Safety**: Session reset actions present a modal confirmation screen (`ConfirmModal`) before wiping session tokens.
5. **Non-TTY Rejection**: Running the interactive TUI in non-interactive environments (pipes/cron) prints a helpful, example-driven guidance message pointing to subcommands and `qwen-web-arwaky doctor`.

### FR-003: Manual Login & Session Setup

The login surface accepts an `AppConfig` and delegates session setup to the Core aggregate. It forces headed mode at configuration construction and reports success after the core verifies the authenticated chat UI.

There is exactly **one** validation gate: `SetupOrchestrator.setup_session` owns the
validate-then-login decision (issue #381). The surface performs no pre-check, so an
expired session costs one headless Chromium cold start before the headed browser
opens, not two. A valid session returns the "already valid" message with no headed
browser at all.

### FR-004: System Diagnostic Command (`doctor`)

The `doctor` subcommand verifies environment health across 5 key dimensions:
1. Python runtime version (>= 3.10)
2. Playwright Chromium browser binary existence
3. Local workspace `.qwen-web/` initialization
4. Session authentication token directory (`qwen_session/`)
5. Output directory write permissions

Supports optional `--json` flag for machine-readable JSON output by AI agents and automated scripts. Supports optional `--smoke` flag for a headless browser smoke test (launch Chromium with the saved session, navigate to `chat.qwen.ai`, verify `textarea.message-input-textarea` is present, close the browser, report pass/fail as a sixth check). `--smoke` requires a valid saved session and a Chromium binary; it reuses `ISessionAggregate.validate_session()` from the Core layer without new capability code.

### FR-005: Self-Update & Environment Synchronization (`update`)

The `update` subcommand delegates the full pipeline to `IUpdateProtocol` (owned by `capabilities_update_manager.py` → `UpdateManager`); the surface formats reports and maps outcomes to the standard success/error response envelope. Pipeline sequence (chronological):

1. **Version discovery** via the GitHub Releases API (pinned to the release's immutable commit SHA; unverified targets are refused, never installed).
2. **Package upgrade** — `git pull` + editable reinstall for PEP 610 editable checkouts, else `pip install` of the pinned SHA.
3. **Playwright Chromium synchronization** — `playwright install chromium`, with a forced cache purge when `--force` is requested.
4. **Post-flight health checks** — Python runtime, package metadata, and Chromium binary presence.

- **`--check`** performs only step 1 (read-only probe); no system changes.
- **`--force`** reinstalls package and browser binaries even when the current version is already up to date.
- **Rollback**: when steps 2–4 are not healthy and the previous version is resolvable, the manager reinstalls the previous pinned SHA plus browser binaries; editable installs skip rollback (source recovery is a `git checkout` operation) and an unknown previous version refuses rollback.

---

## API Contract

| Operation | Input | Output | Production caller |
|---|---|---|---|
| `_parse_args` | argv tokens | `argparse.Namespace` | `modules/root_cli_main_entry.py` |
| `_build_config` | parsed namespace | validated `AppConfig` | `modules/root_cli_main_entry.py` |
| `handle` (run) | args, core | response envelope | `modules/cli/src/surface_cli_run_command.py` |
| `handle` (login) | args, core, cfg | response envelope | `modules/cli/src/surface_cli_login_command.py` |
| `handle` (init) | args, core | response envelope | `modules/cli/src/surface_cli_init_command.py` |
| `handle` (update) | args, core | response envelope | `modules/cli/src/surface_cli_update_command.py` |
| `run_doctor` | json_output flag, smoke flag, session aggregate | process exit code | `modules/cli/src/surface_cli_doctor_command.py` |
| `InteractiveController.run` | optional config | response envelope | `modules/root_cli_main_entry.py` |

---

## Dependency Injection (AR-1)

The TUI surface must not import the Capabilities layer directly (AES layer rules). Slot-input resolution (role-template materialization, path validation, timestamped output naming) is owned by `capabilities_tui_slot_config.py` → `TuiSlotConfigResolver` (`ITuiSlotConfigProtocol`), and the TUI consumes it only through constructor injection of the protocol, wired by the Root container:

- `root_core_container.SharedContainer.tui_slot_config` exposes the resolver as `ITuiSlotConfigProtocol`.
- `surface_cli_interactive_controller.InteractiveController` forwards the injected instance to `QwenTuiApp` (fifth constructor argument, `slot_config`).
- The surface never references `TuiSlotConfigResolver` by concrete class.

Change propagation for a new TUI slot field: contract protocol (`modules/shared/src/contract_core_protocol.py`) → capability resolver (`modules/core/src/capabilities_tui_slot_config.py`) → container wiring (`modules/core/src/root_core_container.py`, unchanged when the resolver class is reused) → surface constructor (`surface_cli_tui_app.py`, `surface_cli_interactive_controller.py`). The integration test `modules/cli/tests/integration_tui_slot_di.py` locks this wiring.

---

## Non-functional Requirements

- **Actionable Error Messages**: Errors specify *what happened*, *why it happened*, and *how to fix it*.
- **Machine-Readable Output**: Subcommands support `--json` for AI agent consumption.
- **Data Safety**: Destructive actions require explicit modal confirmation.
