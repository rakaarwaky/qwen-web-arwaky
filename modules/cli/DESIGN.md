# DESIGN — CLI Surface

> Command-line interaction contract: subcommands, exit codes, envelopes, and
> output formats.
> Audience: CLI users, surface engineers.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [BACKLOG.md](BACKLOG.md) (this surface).

## Brand & Style

Smart surface (AES406). Command modules and controllers dispatch to Root
container aggregates; they carry no domain logic. Console output is plain
text unless `--json` is set; the TUI visual token set lives in
[modules/tui/DESIGN.md](../tui/DESIGN.md), not here.

### Output Channels

| Channel | Usage |
|---|---|
| stdout | Human-readable reports, `--json` envelopes, success messages. |
| stderr | Warnings, `[ERROR]` prefix failures, doctor diagnostic footers. |

## Components

### Entry Points

| Command | Module | Behaviour |
|---|---|---|
| `qwen-web-arwaky` (no args, TTY) | `root_cli_main_entry` → `surface_cli_interactive_controller` | Delegates to the TUI surface (`modules/tui`); the CLI module never imports TUI code at module load — the controller's TUI import is deferred into `run()`, so headless CLI paths stay TUI-free. |
| `qwen-web-arwaky` (no args, config given) | `surface_cli_run_command.dispatch_run` | Headless single-file pipeline run. |
| `init` | `surface_cli_init_command` | Workspace bootstrap: creates `.agents/skills` and `.qwen-web-arwaky` under `--dir` (default: cwd). |
| `doctor` | `surface_cli_doctor_command` | Environment and session health checks; `--smoke` adds a headless browser round-trip; `--json` prints the envelope. |
| `session` | `surface_cli_sessions_command` | Subcommands: `list`, `login --name NAME`, `health`, `remove NAME [--force] [--keep-profile]`, `status`. |
| `prompt direct` | `surface_cli_run_command` | `-t TEXT [-o FILE] [--headless] [--json]` — inline text prompt. |
| `prompt file` | `surface_cli_run_command` | `-i FILE [-o FILE] [--headless] [--json]` — prompt file only. |
| `prompt attach` | `surface_cli_run_command` | `-i FILE -a FILE [-o FILE] [--headless] [--json]` — prompt file plus attachment. |
| `job` | `surface_cli_jobs_command` | Subcommands: `submit`, `status`, `list`, `cleanup`; `--json` available on all. |
| `swarm` | `surface_cli_swarm_command` | Subcommands: `start`, `status`, `cancel`; `--json` available on all. |
| `update` | `surface_cli_update_command` | Flags: `--check`, `--force`, `--json`, `--rollback VERSION`. |
| `observability` | `surface_cli_observability_command` | Subcommands: `report`, `status`; `--json` available on all. |
| `mcp` | `root_mcp_main_entry` | Starts the MCP stdio server; no exit code mapping from the CLI envelope — runs until the client disconnects. |

### Subcommand Flag Matrix

Flags shared by every subcommand in the `prompt`, `job`, `swarm`, and
`observability` groups are registered on the shared parent parser and are
therefore uniformly available:

| Flag | Default | Notes |
|---|---|---|
| `--json` | off | Print the response envelope verbatim as JSON on stdout. |
| `--headless` / `--no-headless` | on | BooleanOptionalAction; off (headed) mode opens a visible browser. |
| `-o FILE` / `--output-path` | `None` | Destination for the Markdown response; omitted only for `job submit` which stores the record in the jobs folder. |

`session login` is the only interactive subcommand that opens a browser;
all other subcommands are non-interactive.

### Exit Codes

| Code | Trigger | Source |
|---|---|---|
| `0` | Success envelope returned | `root_cli_main_entry._result_exit_code` |
| `1` | Failure envelope returned, or unhandled exception caught by `safe_handle` | `root_cli_main_entry._exit_code_for_result`; `utility_core_exit.exit_code_for` |
| `2` | `AuthRequiredError` raised during pipeline execution (session expired, re-login needed) | `utility_core_exit.exit_code_for` |
| `130` | `KeyboardInterrupt` | `utility_core_exit.exit_code_for` |
| `2` | `argparse` usage error (missing required flag, unknown subcommand) | argparse default; exit code `2` is argparse's own, distinct from the auth path |

### Response Envelope

Every non-interactive command returns a standard envelope from
`utility_response_normalizer` (`success_response` / `error_response`):

```json
{ "success": true,  "message": "..." }
{ "success": false, "message": "...", "error_code": "cli-500" }
```

- `--json` prints the envelope verbatim to stdout and exits with the mapped code.
- Without `--json`, human-readable output is printed instead; failures are
  prefixed `[ERROR]` on stderr and the exit code is still mapped from the
  envelope.

Error reference codes used by the CLI surface:

| `error_code` | Meaning |
|---|---|
| `cli-400` | Validation failure (missing required argument, bad path). |
| `cli-500` | Unhandled runtime failure (default from `error_response`). |
| `auth-required` | Session has expired; re-run `qwen-web-arwaky session login`. |

### Output Formats

| Format | Trigger | Shape |
|---|---|---|
| Plain text (default) | No `--json` | One-line status per operation; `doctor` prints a multi-line check table with `PASS`/`WARN`/`FAIL` prefixes. |
| JSON envelope | `--json` | `{"success": bool, "message": str, "error_code"?: str}` on stdout; failures also log a one-line summary to stderr. |
| Markdown file | `-o FILE` on prompt subcommands | The response text, written as Markdown to the named path; not emitted to stdout. |
| Jobs status table | `job list` / `job status` | Human-readable table with `RUNNING` / `COMPLETED` / `FAILED` status per record; `--json` prints the raw `JobRecord` dict. |
| Swarm progress report | `swarm start` / `swarm status` | Compact multi-line report with `⌬ Swarm` header, per-agent status icons (`✓` / `✗` / `⋯`), and progress counts; `--json` prints the `SwarmSnapshot` dict. |
| Update report | `update` / `update --check` | Step list with `[✓]` / `[✗]` / `[–]` icons and detail lines; `--json` prints the `UpdateReport` dict. |

## Reference

- [BACKLOG.md](BACKLOG.md)
- [ROADMAP.md](../../ROADMAP.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [DESIGN.md (TUI)](../tui/DESIGN.md) — visual tokens for the interactive TUI surface.
