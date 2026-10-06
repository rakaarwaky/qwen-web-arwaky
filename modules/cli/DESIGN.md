# DESIGN — CLI and Textual TUI Surface

> Visual and interaction contract. Tokens, scales, and component anatomy.
> Audience: designers, surface engineers, TUI developers.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [BACKLOG.md](BACKLOG.md) (this surface).

## Brand & Style

### Colors

The palette is the Obsidian-dark set the dashboard renders against. Every value
below is a token; a component never names a raw hex.

#### Base Surfaces

| Token | Value | Usage |
|---|---|---|
| `--surface-base` | `#0d1117` | default background behind every panel |
| `--surface-muted` | `#161b22` | card backgrounds, alternate rows, input fields |
| `--surface-elevated` | `#21262d` | overlays, modal confirmation, popups |

#### Primary Accent

| Token | Value | Usage |
|---|---|---|
| `--color-primary` | `#7c3aed` | primary actions, active tab, focus ring, send trigger |

#### Secondary Accent

| Token | Value | Usage |
|---|---|---|
| `--color-secondary` | `#58a6ff` | links, informational highlights, selected slot row |

#### Tertiary Accent

| Token | Value | Usage |
|---|---|---|
| `--color-tertiary` | `#a371f7` | low-emphasis accents, slot status accents |

#### System Diagnostics

| Token | Value | Usage |
|---|---|---|
| `--color-error` | `#ef4444` | error states, validation failures, failed runs |
| `--color-warning` | `#f39c12` | warning states, throttle notices, degraded checks |
| `--color-info` | `#58a6ff` | informational banners, doctor `WARN` rows |
| `--color-success` | `#10b981` | success confirmations, doctor `PASS` rows |

#### Hairlines and Contours

| Token | Value | Usage |
|---|---|---|
| `--hairline-thin` | `1px` | separator lines, table row dividers |
| `--hairline-thick` | `2px` | active tab underline, focused input border |
| `--contour-radius-sm` | `4px` | chips, status badges |
| `--contour-radius-md` | `8px` | cards, panels |
| `--contour-radius-lg` | `12px` | modal confirmation screen |

### Typography

One fixed scale, Major Third `1.250`, with every heading, label, and body
string mapped to a stop. No component introduces a size outside the scale.

| Stop | Size | Role |
|---|---|---|
| `display` | `20px` | panel titles, screen headings |
| `heading` | `16px` | section labels, slot headline |
| `body` | `13px` | prompt output, response text, log lines |
| `label` | `11px` | status badges, column headers, key hints |

### Layout & Spacing

Spacing multiplies from one `4px` base unit. Every declared value is an integer
multiple of it.

| Token | Value | Usage |
|---|---|---|
| `--space-1` | `4px` | badge padding, chip gaps |
| `--space-2` | `8px` | between a label and its control |
| `--space-3` | `12px` | panel internal padding |
| `--space-4` | `16px` | between panels |
| `--space-6` | `24px` | screen margins on a wide terminal |

- One command module per subcommand. A subcommand owns its argument names,
  its validation, and its rendering; it never reaches into another module.
- The interactive controller holds the aggregate seams and the slot table;
  the TUI widgets, compose tree, stylesheet, and workers are separate files
  so a styling change never touches a run path.
- Long operations run in background workers so the terminal canvas stays
  responsive; the interactive path attaches no standard-error log handler,
  because a browser callback writing to it would corrupt the frame.

### Elevation and Depth

| Level | Token | Use case |
|---|---|---|
| `0` | none | default canvas, no shadow |
| `1` | `--shadow-raised` | popovers and the throttle notice floating above the output pane |
| `2` | `--shadow-modal` | the modal confirmation screen and the login screen |

### Shapes

Corners are squared off only where a container edge meets the canvas; every
interactive element carries a contour radius so it reads as pressable.

## Components

### Buttons & Triggers

| Variant | Use case | States | Token map |
|---|---|---|---|
| `send` | submit the prompt from the input area | default / hover / pressed / disabled / focus | `--color-primary`, `--contour-radius-sm` |
| `stop` | cancel an in-flight run | default / hover / pressed / focus | `--color-error`, `--contour-radius-sm` |
| `login` | trigger manual authentication from the login screen | default / hover / pressed / disabled / focus | `--color-primary`, `--contour-radius-md` |
| `confirm` | commit a destructive session action | default / hover / pressed / disabled | `--color-error`, `--contour-radius-md` |

### Status Indicators & Chips

| Variant | Use case | Semantic | Color token | States |
|---|---|---|---|---|
| `slot-status` | per-slot run state in the slot table | success / warning / error / info | `--color-success` / `--color-warning` / `--color-error` / `--color-info` | default / active / muted |
| `session-status` | persisted-session state on a session tab | success / warning / error | `--color-success` / `--color-warning` / `--color-error` | default / active / muted |
| `doctor-row` | one subsystem check in the diagnostics tab | success / warning / error | `--color-success` / `--color-warning` / `--color-error` | default / muted |

### Parallel Stream Cards

| Field | Role |
|---|---|
| icon / glyph | visual anchor for the slot in the table |
| headline | one-line description of the run |
| meta | model name, elapsed time, job id |
| action trigger | stop or rerun for that slot |
| state layer | progress and status indicator |

### Input Fields & Command Bar

| Field | Role | States |
|---|---|---|
| label | field identifier above the input area | default / filled / error / disabled / focus |
| hint | supporting copy naming the next action | default / error |
| input area | the typed prompt | default / hover / focus / disabled |
| suffix | the submit trigger at the trailing edge | default / loading / error |

### Navigation & Tab Bar

| Level | Role | States |
|---|---|---|
| global nav | workspace-level root, back to the action menu | default / hover / focus |
| session tab strip | switch between persisted sessions | default / active / close-hover / focus |
| diagnostics tab | surface the health rows | default / active / focus |

### Entry Points

| Entry point | Caller | Returns |
|---|---|---|
| `init` | operator shell | workspace creation envelope |
| `login` | operator shell, TUI login screen | authentication outcome |
| `doctor` | operator shell, TUI diagnostics tab | health rows, optionally with a smoke gate |
| `sessions` | operator shell, TUI sessions tab | session pool listing |
| `prompt-direct` | operator shell | saved response path |
| `prompt-only` | operator shell | saved response path |
| `prompt-with-attachment` | operator shell | saved response path |
| `update` | operator shell, TUI update action | update report envelope |
| no subcommand on a TTY | operator TTY | interactive dashboard |
| no subcommand without a TTY | operator shell | usage error naming the subcommands |

### Visible States

| State | Shown when | What the operator sees |
|---|---|---|
| Idle | TUI booted, no run active | Slot table with per-slot status badges and the action menu |
| Running | a slot or run is in flight | Streaming assistant text in the output pane, a stop action, and per-event status lines |
| Rate limited | the chat throttled the request | A throttle notice naming the wait before the next attempt |
| Auth required | the saved session expired | The login screen with the destructive re-login choice and a back-to-menu action |
| Failure | the run ended with an error | The error envelope in the output pane, rendered with the error token and its hint |
| Confirming | a destructive action is armed | The modal confirmation screen at elevation level 2 |

## Reference

- [ARCHITECTURE.md](../../ARCHITECTURE.md) owns the layer rules and the filename shape.
- [ROADMAP.md](../../ROADMAP.md) owns the workspace state vocabulary.
- The TUI widgets, compose tree, stylesheet, and workers are separate source
  files so a styling change never touches a run path.

### Assumptions & Constraints

- Every subcommand's result is a structured envelope with a status field,
  so a caller branches on one key instead of sniffing optional keys.
- Output destinations are resolved in one place; a run never invents its
  own filename when the operator named one.
- The interactive surface owns the terminal; no subprocess in that path
  writes directly to it.

### Glossary

- **Smart surface**: a layer that maps parsed arguments and widget values onto
  aggregate requests and renders the response. It decides how work is presented
  and entered, never what the work is.
- **Token**: the single named value a color, size, or spacing decision maps to.
- **Slot**: one parallel run tracked in the slot table, with its own status.
- **Contour**: the border that marks a component's boundary, as distinct from a
  hairline, which separates content inside a component.

- **Product**: [PRD.md](../../PRD.md) owns the product scope these requirements implement.
- **State**: [BACKLOG.md](BACKLOG.md) owns feature status, evidence, and blocked work; the root [ROADMAP.md](../../ROADMAP.md) owns the state vocabulary.
- **Architecture**: Layer boundaries and naming live in [ARCHITECTURE.md](../../ARCHITECTURE.md).
- **Operations**: Command gates and agent workflow live in `AGENTS.md`.

### System Overview

The CLI surface (`modules/cli`) translates command-line arguments and interactive TTY inputs into `AppConfig` objects and delegates execution to the Core aggregate. It remains a **Smart Surface**: presentation, argument validation, dispatch, and lifecycle-boundary concerns belong here; business processing semantics remain in `modules/core`.

The CLI root entry point owns the CLI lifecycle: parse arguments, build `AppConfig`, and dispatch to the Core aggregate. The MCP root is a separate runtime and does not enter the CLI dispatch path.

### Functional Requirements

#### FR-CLI-001: Subcommand Argument Parsing & Config Building

- **Description**: The root parser reads `sys.argv` through a subcommand interface and builds a validated `AppConfig` for the matched surface command.
- **Input**: argv tokens; subcommand, `--model`, output path, `--headless`, `--json` flags.
- **Output**: validated `AppConfig` (`mode`, `model`, `output`, `headless`); the `mcp` subcommand hands control to the MCP entry point.
- **Business Rules**:
  - Model precedence is `--model` > `QWEN_MODEL` > `QWEN_DEFAULT_MODEL` > `Qwen3.8-Max` (issue #283).
  - An unrecognised model name falls back to the first model the picker offers with a WARNING.
  - Argument validation is surface-owned; the surface never invents a default the configuration contract does not specify.
- **Edge Cases**: an unknown subcommand or a missing required argument is an `argparse` error, not a silent default.
- **Error Handling**: an invalid run input is rejected with a non-success exit code and a clear, actionable diagnostic on `stderr`.

| Subcommand | Signal | Result | Validation |
|---|---|---|---|
| `doctor` | `qwen-web-arwaky doctor [--json] [--smoke]` | System health diagnostic | Checks Python, Playwright, workspace, session, permissions; `--smoke` adds a headless browser round-trip (FR-CLI-004). |
| `login` | `qwen-web-arwaky login [--headless]` | `mode="login"` | Forces headed browser for manual authentication unless overridden. |
| `init` | `qwen-web-arwaky init [--dir]` | Workspace initialization | Creates XDG storage directories and root `.qwen-web` symlinks. |
| `prompt-direct` | `qwen-web-arwaky prompt-direct -t "..." [--json]` | Inline text prompt | Direct text string is injected directly. |
| `prompt-only` | `qwen-web-arwaky prompt-only -i FILE [--json]` | `mode="single"` | Prompt file must exist on disk. |
| `prompt-with-attachment` | `qwen-web-arwaky prompt-with-attachment -i FILE -a ATT [--json]` | `mode="single"` + attachment | Prompt file and attachment file must exist on disk. |
| `update` | `qwen-web-arwaky update [--check] [--force]` | Self-update management | Discovers latest release, upgrades package, synchronizes Playwright binaries (FR-CLI-005). |
| `mcp` | `qwen-web-arwaky mcp` | MCP server entry point | Launches the MCP server entry point in-process via uvicorn. |

#### FR-CLI-002: Modern Obsidian Nebula Textual TUI Dashboard

- **Description**: The no-argument TTY fallback launches the interactive Textual dashboard and drives the same `AppConfig`-based pipelines as the subcommands.
- **Input**: TTY input; optional `AppConfig`; slot-input and session state.
- **Output**: rendered dashboard; `PromptResponse` envelopes for every submitted prompt.
- **Business Rules**:
  - Obsidian-dark theme: `#0d1117` background, `#7c3aed` violet accents, `#10b981` green success, `#ef4444` red error, `#f39c12` amber warning.
  - The widget hierarchy is a root TUI app hosting a `StatusPanel` (live `Spinner`, elapsed `Static`), a `PromptPanel` (multiline `Input`), an `OutputPanel` (read-only scrolling log), and a `SessionBar` (session tabs with status icon and close action).
  - The TUI delegates to the same pipeline the subcommands use; it never re-implements prompt execution.
- **Edge Cases**: a missing or expired session renders a login banner and login button instead of crashing; a non-TTY invocation prints guidance instead of launching the dashboard.
- **Error Handling**: a prompt failure surfaces as a panel error carrying the envelope hint; a failed session re-login is offered in place.

Requirements:

1. **Visual Design**: Obsidian-dark theme as specified above.
2. **Component Hierarchy**: root TUI app hosting `StatusPanel`, `PromptPanel`, `OutputPanel`, and `SessionBar`.
3. **Interactivity**: `Enter` submits without leaving the widget; the TUI calls the same `AppConfig`-driven pipeline the CLI subcommands use.
4. **Destructive Action Safety**: session reset actions present a modal confirmation screen before wiping session tokens.
5. **Non-TTY Rejection**: pipes and cron contexts print a guidance message pointing to the subcommands and `doctor`.

#### FR-CLI-003: Manual Login & Session Setup

- **Description**: The login surface accepts an `AppConfig`, delegates session setup to the Core aggregate, forces headed mode, and reports success once the authenticated chat UI is verified.
- **Input**: `AppConfig` with headed mode; persisted session storage path.
- **Output**: setup response reporting session validity and the saved auth state.
- **Business Rules**:
  - Headed mode is set at configuration construction, not discovered later.
  - Exactly one validation gate exists (issue #381), so an expired session costs one headless Chromium cold start before the headed browser opens, not two.
- **Edge Cases**: a valid session returns the already-valid message with no headed browser at all.
- **Error Handling**: an authentication failure returns an actionable setup error naming the next step.

#### FR-CLI-004: System Diagnostic Command (`doctor`)

- **Description**: `doctor` verifies environment health across five dimensions and emits one structured row per check.
- **Input**: `--json` and `--smoke` flags; optional session aggregate.
- **Output**: exit code `0` when no `FAIL` rows, `1` otherwise; JSON rows with `--json`.
- **Business Rules**:
  - The five checks are Python runtime (>= 3.10), Playwright Chromium binary presence, local `.qwen-web/` initialization, session token directory, and output-directory write permissions.
  - `--smoke` adds a sixth check: launch Chromium with the saved session, navigate to the chat UI, confirm `textarea.message-input-textarea` is present, close, and report pass/fail.
  - `--smoke` reuses the Core session-validation path without new capability code.
- **Edge Cases**: every `FAIL` row carries a remediation hint naming the remedy.
- **Error Handling**: a failing subsystem produces a `FAIL` row plus its hint; the command reports all rows before exiting non-zero.

#### FR-CLI-005: Self-Update & Environment Synchronization (`update`)

- **Description**: `update` delegates the full pipeline to the update protocol; the surface formats reports and maps outcomes to the standard response envelope.
- **Input**: `--check` and `--force` flags.
- **Output**: staged update report; `--check` returns the up-to-date/out-of-date verdict.
- **Business Rules**:
  - Version discovery targets an immutable release commit SHA; unverified targets are refused, never installed.
  - PEP 610 editable checkouts use pull + editable reinstall; otherwise the pinned SHA is installed with the package manager.
  - Playwright Chromium is re-synchronized after the package step, with a forced cache purge under `--force`.
  - Post-flight health checks cover Python runtime, package metadata, and Chromium binary presence.
- **Edge Cases**: an unknown previous version refuses rollback; editable installs skip rollback because source recovery is a `git checkout` operation.
- **Error Handling**: a failed stage stops the update and reports the remedy, never leaving a half-upgraded install unreported.

### API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `IDirectPromptProtocol.process_direct_prompt(prompt, model, output, headless)` | prompt text, model, output path, headless flag | response envelope | missing dependencies or processing failure | prompt lifecycle events | Runs an inline text prompt against the authenticated chat session. |
| `IPromptFileProtocol.process_prompt_file_only(file, model, output, headless)` | prompt file path, model, output, headless | response envelope | prompt file missing or unreadable | prompt lifecycle events | Runs a prompt read from a file. |
| `IAttachmentPromptProtocol.process_prompt_with_attachment(file, attachment, model, output, headless)` | prompt file, attachment, model, output, headless | response envelope | file or attachment missing or unsupported | prompt lifecycle events | Runs a prompt with a file attachment. |
| `ISessionAggregate.check_session(storage_path)` | session storage path | session-valid verdict | storage unreadable | — | Verifies the persisted authenticated session. |
| `ISetupAggregate.setup_session(headed_context)` | headed browser context | login-complete verdict | authentication not completed or browser launch failed | login complete | Manual login and session setup. |
| `IUpdateProtocol.check_update()` / `IUpdateProtocol.perform_update(force)` | force flag | update report with per-stage results | a failed stage stops the sequence and reports the remedy | update stages | Self-update and Playwright binary synchronization. |
| `IWorkspaceProtocol.init_workspace(target_dir)` | target directory | created workspace paths | unwritable target | — | Creates XDG storage directories and root symlinks. |
| `ISlotRunPlanProtocol.resolve(plan, workspace)` | slot inputs (role template, paths, output name) | resolved slot-run plan | invalid role template or path | — | TUI slot-input resolution behind constructor injection. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| run-command `handle(args, cfg, direct, file_only, attachment)` | parsed args, `AppConfig`, prompt protocols | response envelope | a Core failure surfaces as a structured error | prompt lifecycle events | Subcommands `prompt-direct`, `prompt-only`, `prompt-with-attachment`. |
| login-command `handle(args, session, setup, cfg)` | parsed args, session/setup aggregates, `AppConfig` | response envelope | login not completed | login complete | Subcommand `login`. |
| init-command `handle(args, workspace)` | parsed args, workspace protocol | response envelope | unwritable workspace | — | Subcommand `init`. |
| update-command `handle(args, updater)` | parsed args, update protocol | staged update report | stage failure with remedy | update stages | Subcommand `update`. |
| doctor-command `run_doctor(json_output, smoke, session)` | doctor flags, optional session aggregate | process exit code | — | — | Subcommand `doctor`. |
| TUI `InteractiveController.run(cfg, *, prompt)` | optional `AppConfig` | response envelope | TUI boot failure reported in-panel | prompt lifecycle events | No-argument TTY fallback driving the interactive TUI. |

#### Dependency Injection (AR-1)

The TUI surface must not import the Capabilities layer directly (AES layer rules). Slot-input resolution (role-template materialization, path validation, timestamped output naming) is owned by the slot-plan resolver capability (`SlotRunPlanResolver`, exposed as `ISlotRunPlanProtocol`), and the TUI consumes it only through constructor injection of the protocol, wired by the Root container:

- The shared root container exposes the resolver as the slot-run-plan protocol.
- The interactive CLI controller forwards the injected instance to the TUI app (fifth constructor argument, `slot_config`).
- The surface never references the concrete resolver class.

Change propagation for a new TUI slot field: contract protocol (the slot-run-plan protocol in the shared contract layer) -> slot-plan resolver capability -> container wiring (unchanged when the resolver class is reused) -> surface constructor (the TUI app and the interactive CLI controller). The TUI slot-DI integration test locks this wiring.

### Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| `chat.qwen.ai` | outbound | The single external endpoint every prompt path targets. | Headed login required first; network or auth failure surfaces as a structured error envelope. |
| Core aggregate (prompt, session, setup, update, config, jobs) | outbound | The CLI delegates all prompt execution, session management, setup, and self-update to the Core aggregate. | A Core error envelope is re-emitted as a structured CLI error with a remediation hint. |
| Playwright Chromium | outbound | Headed and headless browser lifecycle owned by the Core; the surface only supplies flags. | Missing Chromium or a sandbox blocker is reported by `doctor`; the surface refuses to run with an actionable hint. |
| XDG storage and root `.qwen-web` symlinks | read/write | Persistent session, job state, and generated output live here. | Unwritable storage is reported by `doctor` and `init`. |
| GitHub Releases API | outbound | Release discovery and immutable commit SHA resolution for `update`. | An unverified target is refused and reported; no install is attempted. |

### Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Actionable error messages | Every CLI failure prints what happened, why it happened, and how to fix it | All subcommand and TUI error paths carry a remediation hint; `doctor` reports a hint on every `FAIL`. |
| Machine-readable output | Every subcommand supports `--json` for AI agent consumption | `--json` present and valid in each subcommand `--help`; JSON payload valid against the envelope shape. |
| Data safety | Destructive actions require explicit modal confirmation | TUI confirmation modal and the `delete_session` confirm gate. |
| Unattended update | `update` runs without interactive authentication | `update` accepts only flags; no TTY prompt. |
| Layer discipline | The TUI never imports the Capabilities layer | Architecture scanner on the touched paths. |

### Test Scenarios

- Subcommand matrix: each subcommand builds the correct `AppConfig` mode; a missing or malformed argument surfaces a structured validation error.
- TUI boot: the no-argument TTY fallback renders the dashboard; a non-TTY invocation prints guidance instead of launching the dashboard.
- Login gate: an expired session drives the single validation gate; a valid session returns already-valid with no headed browser.
- Doctor: `--smoke` completes a headless round-trip and exits `0` when healthy, `1` on any `FAIL` row.
- Update: `--check` reports up-to-date without installing; a failed stage stops the sequence and prints the remedy.
- Slot injection: a new slot field propagates contract to capability to container to surface without a surface-layer import.

### Assumptions & Constraints

- One persistent Chromium session profile per host; login is interactive and headed.
- The MCP root is a separate runtime and never enters the CLI dispatch path.
- The TUI is presentation-only: all business semantics live in the Core aggregate.
- Generated responses are written to the `-o/--output` path the user names; the surface never invents a default.
- An editable checkout rolls back through source recovery, not reinstall.

### Glossary

- **Smart Surface**: a layer that owns presentation, argument validation, dispatch, and lifecycle boundaries but not business processing semantics.
- **Core aggregate**: the composite entry points (prompt, session, setup, update, config, jobs) the CLI delegates to.
- **Slot plan**: the per-TUI-run materialization of role-template inputs, paths, and output naming.
- **`AppConfig`**: the validated configuration object the surface builds from arguments and passes to the Core aggregate.
- **PEP 610 editable checkout**: an installed-from-source tree whose version metadata points at a working directory rather than a published artifact.

### Backlog

Feature status, evidence, and blocked work for this surface live in [BACKLOG.md](BACKLOG.md).
