# DESIGN — CLI Surface

## Design Overview

A smart surface (AES406) for `qwen-web-arwaky`: command modules and controllers dispatch to Root container aggregates and carry no domain logic. Console output is plain text unless `--json` is set; the TUI visual token set lives in [modules/tui/DESIGN.md](../tui/DESIGN.md), not here.

## Design Requirements

### DS-CLI-001: Output Channels

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| stdout | Human-readable reports, `--json` envelopes, success messages | `stdout` | default sink |
| stderr | Warnings, `[ERROR]`-prefixed failures, doctor diagnostic footers | `stderr` | diagnostic sink |

### DS-CLI-002: Entry Points

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `qwen-web-arwaky` (no args, TTY) | Delegates to the TUI surface | `surface_cli_interactive_controller` | TUI import deferred into `run()` |
| `init` | Workspace bootstrap under `--dir` | `surface_cli_init_command` | creates `.agents/skills`, `.qwen-web-arwaky` |
| `doctor` | Environment and session-pool health; `--smoke`, `--deep` | `surface_cli_doctor_command` | pool is the single source of truth |
| `session` | `list`, `login`, `health`, `remove`, `status` | `surface_cli_sessions_command` | `remove` confirms on a TTY |
| `prompt` | `direct` (`-t`), `file` (`-i`), `attach` (`-i -a`) | `surface_cli_run_command` | inline, file-only, file+attachment |
| `job` | `submit`, `status`, `list`, `cleanup` | `surface_cli_jobs_command` | `--json` on all |
| `swarm` | `start`, `status`, `cancel` | `surface_cli_swarm_command` | `--json` on all |
| `update` | `--check`, `--force`, `--rollback` | `surface_cli_update_command` | `--json` |
| `observability` | `report`, `status` | `surface_cli_observability_command` | `--json` on all |

### DS-CLI-003: Exit Codes

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `0` | Success envelope returned | `_result_exit_code` | success |
| `1` | Failure envelope or unhandled exception | `_exit_code_for_result` | failure |
| `2` | `argparse` usage error (missing flag, unknown subcommand) | argparse | usage signal |
| `3` | `AuthRequiredError` / auth-failure envelope | `exit_code_for` | re-login needed |
| `130` | `KeyboardInterrupt` | `exit_code_for` | SIGINT |

### DS-CLI-004: Response Envelope

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Success | `--json` or human-readable default | `success_response` | `{ "success": true, "message": "..." }` |
| Failure | Mapped to the exit code | `error_response` | `{ "success": false, "message": "...", "error_code": "..." }` |

### DS-CLI-005: Error Reference Codes

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Validation failure | Missing argument, bad path, unknown id | `cli-400` | reject before dispatch |
| Processing failure | Request well formed, pipeline could not complete | `cli-422` | prompt / self-update |
| Saturated pool | Worker pool refused a job submit | `cli-429` | `JobQueueFullError`, retry hint |
| Unhandled runtime failure | Default from `error_response` | `cli-500` | generic runbook |
| Update-specific failure | Check or rollback machinery errored | `cli-502` | update runbook |
| Auth required | Session expired | `auth-required` | `session login` |

### DS-CLI-006: Shared Flags

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `--json` | Print the envelope verbatim on stdout | off | available on every subcommand |
| `--headless` / `--no-headless` | Headless by default; off opens a visible browser | on | `BooleanOptionalAction` |
| `-o FILE` | Destination for the Markdown response | `None` | omitted only for `job submit` |
| `--deep` | Heavy Playwright probe on `doctor` | off | alias `QWEN_DOCTOR_DEEP=1` |

### DS-CLI-007: Status Glyphs

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Result glyphs | ✓ / ✗ / ⚠ | `STATUS_GLYPHS` | shared Taxonomy object |
| Health glyphs | ● / ◐ / ⛔ / ○ | `STATUS_GLYPHS` | `surface_cli_json_hook` re-export |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](../../PRD.md) |
| Backlog | Task tracking, epics, and implementation status | [BACKLOG.md](BACKLOG.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
| TUI Design | Visual tokens for the interactive TUI surface | [DESIGN.md](../tui/DESIGN.md) |
