# DESIGN — CLI Surface

> Command-line contract: subcommands, output envelopes, and exit codes.
> Audience: CLI users, surface engineers.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [BACKLOG.md](BACKLOG.md) (this surface).

## Brand & Style

### Kind

Smart surface (AES406). Command modules and controllers dispatch to Root
container aggregates; they carry no domain logic.

## Components

### Entry Points

| Command | Module | Behaviour |
|---|---|---|
| `qwen-web-arwaky` (no args, TTY) | `root_cli_main_entry` → `InteractiveController` | Delegates to the TUI surface (`modules/tui`); the CLI module itself never imports TUI code at module load — the controller's TUI import is deferred into `run()`, so headless CLI paths stay TUI-free. |
| `qwen-web-arwaky` (no args, config given) | `surface_cli_run_command.dispatch_run` | Headless single-file pipeline run. |
| `prompt direct` / `prompt file` / `prompt attach` | `surface_cli_run_command` | Non-interactive pipeline execution, Markdown out at `-o`. |
| `doctor` | `surface_cli_doctor_command` | Environment and session health checks. |
| `sessions` | `surface_cli_sessions_command` | List/rotate/delete saved sessions. |
| `jobs` | `surface_cli_jobs_command` | Job folder storage and status inspection. |
| `swarm` | `surface_cli_swarm_command` | Multi-account swarm orchestration. |
| `update` | `self.surface_cli_update_command` | Update check via `IUpdateCheckProtocol`. |
| `init` | `surface_cli_init_command` | Workspace bootstrap. |
| `observability` | `surface_cli_observability_command` | Log/metrics inspection. |

## Reference

### Response Contract

Every command returns the standard envelope from
`utility_response_normalizer` (`success_response` / `error_response`):
`{"success": bool, "message": ..., "error_code": ...}`. Exit code maps from
`success` via `_result_exit_code`; `--json` prints the envelope verbatim.

### Separation from TUI

The TUI layer lives in `modules/tui` and depends on this module (doctor
checks, command dispatch). This module must never import `modules.tui` at
module load time; the single deferred import inside
`surface_cli_interactive_controller.run()` is the only CLI→TUI edge, and it
executes only in interactive mode.
