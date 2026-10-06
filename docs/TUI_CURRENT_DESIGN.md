# Qwen Web Automation TUI — Current Text Design

Reference document for a redesign. Describes the TUI exactly as it exists
today: structure, every button, every label, colors, interactions, and
keyboard behavior. Source of truth: `modules/cli/src/surface_cli_tui_*.py`.

Sections 3, 4, 5, 6, 9, and 13 reflect the mobile-web mockup port from
`design/overview_engine_status`, `design/login_session_manager`,
`design/slot_chat_automation_console`, and `design/swarm_multi_agent_stream`.

App title bar: `QWEN-CLI <version>` · subtitle: `chat.qwen.ai parallel
automation engine`.

---

## 1. Global Layout

```text
┌─ Header (height 3, dock top, clock right) ─────────────────────────────┐
│ Tabs: [Overview] [Sessions] [Swarm] [Slot 1 ●] … [Slot N ●]            │  ← height 3
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Active tab pane (fills remaining height, 1fr)                          │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ Footer (height 1, dock bottom): key hints from BINDINGS                │
└────────────────────────────────────────────────────────────────────────┘
```

- Tab strip is horizontally scrollable (`overflow-x: auto`).
- Slot tabs render live status: `Slot N ●` idle, `Slot N: <file> ▶` running,
  `Slot N: <file> ✓` success, `Slot N: <file> ✕` failed, `Slot N ■` cancelled,
  `Slot N ⚠ CANCELLING…` cancelling. Filename truncated to 12 chars + `…`.
- Slot count = `max(2, DEFAULT_MAX_WORKERS)` (10 by default).

---

## 2. Design Tokens — "Obsidian Terminal"

Single source of truth: `_COLORS` in `surface_cli_tui_css.py`, emitted as CSS
variables. Palette sourced from `design/obsidian_terminal/DESIGN.md`.

| Token | Hex | Role |
| --- | --- | --- |
| `fg_accent` | `#8ed5ff` | Header text, pane titles, accent labels, focus borders |
| `fg_primary` | `#dfe2ee` | Default body text, field labels, table text |
| `fg_muted` | `#bdc8d1` | Inactive tab text, subtext, section labels, hints |
| `fg_on_accent` | `#00354a` | Text on accent-filled buttons |
| `accent` | `#38bdf8` | Footer background, active switch, primary accents |
| `bg_base` | `#0f131c` | App background, log panels |
| `bg_surface` | `#0a0e16` | Tab strip, tables, left pane, modals |
| `bg_raised` | `#1c2028` | Inputs, card-inner tiles, retry button, session badge |
| `bg_overlay` | `#181c24` | Card containers, right (log) pane of slot tabs |
| `bg_hover` | `#262a33` | Browse buttons, copy buttons, hover states |
| `bg_active` | `#31353e` | Active tab background, hovered highlights |
| `border` | `#3e484f` | Default 1px borders (outline-variant) |
| `status_ok` | `#56e5a9` | SUCCESS status, session VALID, tertiary beacon |
| `status_warn` | `#c0c1ff` | Retry button, TIMEOUT, warning emphasis (secondary) |
| `status_err` | `#ffb4ab` | Errors, cancel borders (error) |
| `status_info` | `#38bdf8` | INFO log level (primary-container) |
| `status_muted` | `#87929a` | DEBUG log level (outline) |
| `bright` | `#56e5a9` | Log emphasis (TEMPLATE:, INIT:) — matches ok |
| `danger_bg` | `#93000a` | Cancel-slot button background (error-container) |
| `danger_fg` | `#ffdad6` | Text on danger background (on-error-container) |

Typography conventions:
- Field / section labels: `fg_muted`, bold, uppercase feel via short captions.
- Pane titles: `fg_accent`, bold, on `bg_base`, bottom border, height 3.
- No font-size scale exists (Textual = monospace cell grid); hierarchy comes
  from color, bold, borders, and spacing (padding/margin units = 1 cell row).

---

## 3. Tab 1 — Overview (`tab-overview`)

Brand row (`>_ QWEN-CLI` + version chip), then every block in the mockup's
order inside one scroll band (`.overview-scroll`, `height: 1fr`,
`overflow-y: auto`). The band is the only element that gives up rows on a
short terminal, so the log card keeps its height at every size.

1. **Telemetry banner** (`.screen-card.metric-card`, `bg_overlay`, bordered,
   no vertical padding → 4 rows) holding two `bg_raised` tiles split by a
   one-column gap:
   - **Tile 1** — caption `● ACTIVE ACCOUNTS` (`#metric-active-label`) over
     value `#metric-active` (bare RUNNING-slot count) plus the unit label
     `Active`.
   - **Tile 2** — caption `⊕ MODEL` (`#metric-model-label`) over
     `#metric-model`, printed in `primary_fixed` (`#c4e7ff`).
2. **Engine card ×2** (`.screen-card.engine-card`, 7 rows each): icon chip
   (`.card-icon`) plus the card title (`#metric-swarm-label` /
   `#metric-threads-label`), the inset bento (`.engine-bento`, 3 rows) and the
   per-slot cluster bar.
   - **Ring** (`#metric-swarm-ring` / `#metric-threads-ring`) — accent-bordered
     box holding the `n/m` count (swarm agents / slot threads).
   - **Detail** — `Idle` or `N Running` (`#metric-swarm-detail`); the chat card
     adds the `Active Threads` sub-caption over `N Running · N Idle`
     (`#metric-threads-detail`).
   - **Uptime** (swarm card only, `#metric-swarm-uptime`) — right-aligned;
     `Uptime Elapsed —` while idle, split onto two lines
     (`Uptime Elapsed` / `21m 53s`) once a run is live.
   - **Cluster bar** (`#metric-swarm-bar` / `#metric-threads-bar`) — one
     tinted segment per job slot stretched across the card. This bar is the
     per-slot indicator: each segment recolours with its slot's state, and it
     re-tints on resize from the bar's own width.
3. **System Event Log card** (`.screen-card.log-card`, `bg_surface`): header
   row (`● [ SYSTEM EVENT LOG ]` … `● LIVE STREAM` + the `Copy` button
   `#btn-copy-log`) over `#log-view-overview` (RichLog, wrap, auto-scroll,
   2000 lines, `height: 7` → 6 content rows).

Session state is no longer a badge on the Overview: `_check_session` writes
the verdict (`VALID` / `EXPIRED` / `N/A` / `TIMEOUT`) to this log and to
`_last_session_state`, and the Sessions screen carries the per-account health
state.

Startup message in log: `Qwen Web Automation TUI initialized with multi-slot
architecture.` / `Each slot runs an independent Chromium process sharing
login state.`

---

## 4. Tab 2 — Sessions (`tab-sessions`)

Layout follows `design/login_session_manager` — the primary account action
sits full-width above the pool, and the pool title row carries the utility
action.

1. **Metric tile strip** (`.card-inner`):
   - `REGISTERED` + value `0`
   - `HEALTHY` + value `0` (metric-ok, green)
   - `LIMITED` + value `0`
2. **Primary account button** — **`＋ ADD ACCOUNT`** (`#btn-sessions-login`,
   `.btn-primary-full`, `variant="primary"`, full width, height 3) — opens
   SessionSetupScreen (currently falls back to a notify telling the user the
   CLI command).
3. **Pool title row** (`.pane-title`): `ACCOUNT POOL` label +
   **`🔄 Re-check Tokens`** (`#btn-sessions-refresh`, `.btn-copy-log`) —
   reloads the session pool into the table.
4. **Sessions table** (`#sessions-table`): `ID` | `Name` | `Status` |
   `Last Used` | `Path`
5. **Button row** (`.toggle-row`, bordered, height 3):
   - **`🏥 Health Check`** (`#btn-sessions-health`) — runs
     `SessionHealthChecker` on the pool, logs `HEALTH CHECK: n/m sessions
     healthy.`, refreshes table.
6. **Log view** (`#log-view-sessions`, 500 lines).

---

## 5. Tab 3 — Swarm (`tab-swarm`)

Vertical stack inside `.swarm-screen`, in the mockup's order.

1. **Attachment card** (`.screen-card.swarm-file-card`, 3 rows): file icon
   (`#swarm-file-icon`) + resolved name (`#swarm-file-name`, starts as
   `No file attached`) + **`⇪ Browse`** chip (`#btn-browse-swarm-file`) →
   FilePickerModal in directory-select mode. The chip is a one-row ghost
   because the default three-row Button overflowed the card and rendered as
   an empty box.
2. **View toggle row** (`.output-inspection`, 1 row): caption
   `OUTPUT INSPECTION` + segmented switch `#btn-swarm-event` (Event Log) /
   `#btn-swarm-system` (`log system`). Exactly one of the two log views in
   the card below stays visible.
3. **Log card** (`.screen-card.swarm-log-card`, `1fr`, min-height 8):
   - header row `.swarm-log-head` — path `/var/log/qwen-swarm.pool.log` +
     **`🗑 Clear`** (`#btn-clear-swarm-log`), hairline under it;
   - `#log-view-swarm` (event, visible by default) and
     `#log-view-swarm-system`, both `.swarm-log-view` (wrap, auto-scroll,
     2000 lines);
   - footer row — `>` caret + `Listening on unix socket
     /run/qwen-swarm.sock...` (`#listener-line`).
4. **Action deck** (`.swarm-action-deck`, 3 rows): **`■ Stop`**
   (`#btn-swarm-cancel`, raised surface, error text) + **`↻ RESTART`**
   (`#btn-swarm-start`, accent fill, twice the width). RESTART validates the
   attachment; at ≥4 browsers it confirms through `ConfirmModal "Swarm
   Resource Usage"` first.
5. Hidden `#input-swarm-file` — the Browse chip drives its value.

The mockup has no agent table, so per-agent progress is reported to the log
instead: `_render_swarm_snapshot` writes a line per agent whose status or
attempt changed, plus an aggregate line, and skips an unchanged snapshot
because the worker polls once a second. The swarm worker's own status lines go
to this panel through `_log_swarm_msg`, not to the Overview log.

---

## 6. Tabs 4…N — Job Slot Consoles, and the Settings pane

### 6.1 Slot console (`tab-slot-N`)

Each slot tab is the chat console from `design/slot_chat_automation_console`:

```text
┌ slot carousel (3 rows, ten 1fr pills, no scrollbar) ──────────────┐
│  ● 01  ● 02  ● 03 …                                             │
├──────────────────────────────────────────────────────────────────┤
│ [Event Log] [System Log]                        ● READY ●         │  ← telemetry header
│ Pick a prompt file, or type a task below to get started.          │  ← transcript
│ ┌ EVENT LOG [SLOT #1]  Copy ────────────────────────────────────┐ │  ← event log card (1fr)
│ └────────────────────────────── 12:04:30 ───────────────────────┘ │
│ [ > Type automated task or command...                    ]      │
└──────────────────────────────────────────────────────────────────┘
```

A task is typed into the composer below the event log card and sent. The
execution surface is the composer: a prompt role typed there materializes the
template through the same resolver a run takes, and a free-text task goes
through the direct-prompt path. The registry overrides on the Settings pane
shape every run. The Upload / Attach / Templates pill row that used to sit
between the log card and the composer is gone with the per-slot form it drove;
typed text in the composer covers both paths.

- The slot carousel pills split the row (`width: 1fr`, `overflow-x: hidden`)
  and relabel themselves: `● SLOT 07` while the row has the twelve columns a
  pill needs, `● 07` below that (`_refresh_slot_chips`).
- The transcript sizes to its content up to 12 rows; the log card takes
  every leftover row, so the console fills the screen and the composer stays
  put. The whole console needs about 29 rows; below that the pane clips.
- A carousel pill press switches the slot in one click and carries the focus
  with it (`_switch_to_slot`), because Textual makes the pane holding the
  focused widget the active tab.

### 6.2 Settings pane (`tab-settings`)

**Configuration only.** The pane is the runtime-override surface and nothing
else: one row per registered environment value, `Apply`/`Reset` per row. It
carries **no slot selector, no prompt file, no attachment path, and no run
controls** — those belong to a job, not to the application. The per-slot
form they lived in (and its second copy on the slot console) is gone; the
composer on the slot console is the execution surface, and the override card
is the whole of Settings.

No mockup ships for this screen, so it follows the same card language as the
Overview and Swarm consoles.

#### Runtime Overrides

The whole pane. Every value in the environment registry
(`REGISTERED_ENV`, the same table `qwa doctor` prints) gets one row: the
variable name, what it does, the value in force, an `Apply` and a `Reset`
control. The defaults are the product — this screen only adjusts them — so an
empty field means "back to the default", never "set to empty".

```text
┌ ⚙ RUNTIME OVERRIDES ──────────────────────────────────────────────┐
│ ENVIRONMENT                          DEFAULT · production           │
│ deployment mode; switches log … · default: production              │
│ [production                                     ] [Apply] [Reset]  │
│ ────────────────────────────────────────────────────────────────── │
│ QWEN_WEB_MAX_WORKERS          RESTART · executor pool built at start│
│ job-executor worker count … · default: auto                        │
│ [6                                            ] [Apply] [Reset]  │
└──────────────────────────────────────────────────────────────────┘
```

17 rows at 7 rows each is 119 rows of content in a 34-row band, so
`#settings-overrides` is the only thing on the screen that scrolls; the nav
dock below it stays put.

| Element | id | Behavior |
| --- | --- | --- |
| Value field | `override-input-NAME` | Shows the effective value; the registry default when nothing overrides it. Secrets render masked (`***`). |
| `Apply` | `override-apply-NAME` | Validates through the registry's own `validate_env`, writes to `os.environ` **and** the override file, re-renders the row. Enter in the field takes the same path. |
| `Reset` | `override-reset-NAME` | Drops the override from the file and the environment; the default takes over. |
| State badge | `override-badge-NAME` | `DEFAULT · <default>`, `ACTIVE NOW`, or `RESTART · <reason>`. |

Six values are read only at start-up and carry a `RESTART` badge:
`QWEN_WEB_MAX_WORKERS`, `PLAYWRIGHT_BROWSERS_PATH`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_SERVICE_NAME`, `SENTRY_DSN`, `ENVIRONMENT`. Everything else applies to
the next run or Swarm start in the same session.

Override records go to the Overview event log, not to a slot's event log: a
change to a process-wide value belongs to no single slot.

#### Where overrides are stored

`~/.config/qwen-web-arwaky/settings.env` (XDG config home), one `NAME=VALUE`
per line, in the same shape as a shell fragment. The CLI entry calls
`install_settings()` before the container is built, so a value applied in the
TUI is in force for the run that reads it.

Precedence, weakest to strongest: registry default → settings file → process
environment. A shell export therefore always beats the file, and a value the
registry rejects is dropped on load and on save rather than silently changing
behaviour on the next start.

Implementation: `modules/shared/src/utility_core_env.py` (`settings_path`,
`load_settings`, `save_settings`, `install_settings`, `clear_settings`) and
`modules/cli/src/surface_cli_tui_settings.py` (`_TuiSettingsMixin`). The
override file lives in the same module as the registry it persists, because a
second utility importing the first would break the layer's no-utility-imports
rule.

---

## 7. Modals & Secondary Screens

### 7.1 FilePickerModal (`FilePickerModal`)

- Centered overlay, dim background `rgba(15, 19, 28, 0.85)`, container 80%×80%,
  double accent border.
- Title bar: `[ SELECT FILE — press Enter on file to select ]` or
  `[ SELECT FILE OR FOLDER — press Enter on a file, or click 'Select This
  Folder' ]`.
- Body: `DirectoryTree` rooted at CWD.
- Buttons (right-aligned): **`Select This Folder`** (primary, only in
  directory mode) · **`Cancel (Esc)`** (hover → danger red).
- Esc cancels; Ctrl+S selects folder; focus returns to the invoking Browse
  button on dismiss.

### 7.2 HelpScreen (`?` key)

- Centered overlay `rgba(15, 19, 28, 0.9)`, width 72 cols, double accent border.
- Title: `[ KEYBOARD SHORTCUTS ]`.
- Body lines (live-rendered for actual slot count):

```text
alt+0            Overview tab
alt+1 .. alt+9   Slots 1-9
ctrl+alt+0..9    Slot 10-19
enter / ctrl+r   Run active slot
ctrl+x           Cancel active slot
ctrl+c           Copy active log to clipboard
ctrl+alt+s       Swarm tab
ctrl+l           Login / session setup
ctrl+i           Init workspace
ctrl+q           Quit (confirm when jobs running)
alt+left         Previous slot
alt+right        Next slot
escape           Dismiss modal / quit when idle
?                This help screen
```

- Button **`Close`**; Esc/Q dismiss.

### 7.3 ConfirmModal (destructive-action gate)

- Title uppercased, bold red; message plain; buttons: **`Cancel`**
  (focused by default — Enter never confirms) · confirm button in
  `variant="error"` with contextual label (`Quit and Cancel Jobs`,
  `Cancel Slot`, `Start Swarm`, `Delete Session & Login Again`).
- Keys: `y` confirm, `n`/`Esc` cancel.

### 7.4 SessionSetupScreen (login path, `ctrl+l` or `🔐 Add Session`)

- Status line: `Session status: <state>` (state = `N/A`, `VALID`,
  `EXPIRED`, `TIMEOUT`, `CHECKING`, each suffixed with
  `— run 'qwen-web-arwaky doctor' for diagnostics` when applicable).
- Buttons: **`Delete Session & Login Again`** (error variant) →
  ConfirmModal `"Confirm Session Reset"` ("Are you sure you want to delete
  your saved browser session? You will need to log in again manually.") →
  blocking login worker. **`Back to Main Menu`** (default).
- While logging in: Overview badge shows `LOGGING IN…`; result logged as
  `LOGIN RESULT:` / `LOGIN FAILED:`.

---

## 8. Status System

### Slot status (one value → two render targets)

| State | Badge (slot right pane) | Table cell / tab hint |
| --- | --- | --- |
| IDLE | `● READY` | `IDLE ●` |
| RUNNING | `▶ RUNNING` | `RUNNING ▶` |
| SUCCESS | `✓ SUCCESS` | `DONE ✓` |
| FAILED | `✕ FAILED` | `FAILED ✕` |
| CANCELLED | `■ CANCELLED` | `CANCELLED ■` |
| CANCELLING | `⚠ CANCELLING…` | `CANCELLING ⚠` |

### Event-level badges (while RUNNING; key = pipeline event)

`⚠ RECONNECTING`, `◌ LOADING`, `⇪ UPLOADING`, `✎ PROMPTING`, `⊞ PARSING`,
`→ SENDING`, `✓ SENT`, `◔ THINKING`, `≡ STREAMING`, `✓ FINISHED`,
`✓ SAVED`, `✓ LOGGED IN`, `✓ MODEL`, `✕ FAILED`.

Table cells prefix event badges with `RUNNING ▶ · ` for scanability.

Glyph rule: monospace single-width glyphs only (no emoji in status columns),
to keep column widths stable.

---

## 9. Complete Button Inventory

| # | Label | Location | id | Variant / style |
| --- | --- | --- | --- | --- |
| 1 | `📋 Copy` | Overview log title | `btn-copy-log` | default, accent text |
| 2 | `＋ ADD ACCOUNT` | Sessions primary row | `btn-sessions-login` | primary (`.btn-primary-full`) |
| 3 | `🔄 Re-check Tokens` | Sessions pool title row | `btn-sessions-refresh` | default |
| 4 | `🏥 Health Check` | Sessions toggle row | `btn-sessions-health` | default |
| 5 | `Browse` | Swarm file field | `btn-browse-swarm-file` | width 8, accent text |
| 6 | `EVENT LOG` | Swarm log toggle | `btn-stream-view` | `.segswitch-btn` (active by default) |
| 7 | `SYSTEM LOG` | Swarm log toggle | `btn-log-view` | `.segswitch-btn` |
| 8 | `📋 Copy` | Swarm event log title | `btn-copy-swarm-log` | default |
| 9 | `Clear` | Swarm system log title | `btn-clear-swarm-log` | default |
| 10 | `■ STOP` | Swarm action deck | `btn-swarm-cancel` | `.btn-stop` |
| 11 | `▶ START` | Swarm action deck | `btn-swarm-start` | `.btn-start`, primary |
| 12 | `Send` | Slot composer | `btn-send-N` | `.btn-send` |
| 13 | `📋` | Slot log title | `btn-copy-log-N` | icon-only, tooltip |
| 14 | `Select This Folder` / `Cancel (Esc)` | File picker modal | `btn-select-folder` / `btn-cancel-modal` | primary / default |
| 15 | `Close` | Help modal | `help-close` | default |
| 16 | `Cancel` / confirm label | Confirm modal | `btn-cancel` / `btn-confirm` | default / error |
| 17 | `Delete Session & Login Again` / `Back to Main Menu` | Session setup | `login` / `back` | error / default |
| 18 | `Apply` / `Reset` | Settings override row | `override-apply-NAME` / `override-reset-NAME` | `.btn-apply` |

Interactive non-button controls: one `Input` per slot (`composer-N`, the
free-text task), the swarm file input, one `Input` per Settings override row
(`override-input-NAME`).


---

## 10. Keyboard Model

| Key | Action |
| --- | --- |
| `Alt+0` | Overview tab |
| `Alt+1…9` | Slot 1…9 |
| `Ctrl+Alt+0…9` | Slot 10…19 |
| `Ctrl+Alt+S` | Swarm tab |
| `Alt+Left` / `Alt+Right` | Prev / next slot tab |
| `Enter` / `Ctrl+R` | Run the active slot's typed composer text through the resolver; empty composer gives a "Prompt file is required." notice |
| `Ctrl+X` | Cancel active slot |
| `Ctrl+C` | Copy active tab's log to clipboard (toast: `Copied N log lines to clipboard`) |
| `Ctrl+L` | Login / session setup |
| `Ctrl+I` | Init workspace (logs `INIT: Workspace initialized in <cwd>`) |
| `Ctrl+Q` | Quit — confirm modal if jobs running; else requires second Esc within 2s |
| `Esc` | Dismiss modal, or quit when idle (same double-press guard) |
| `?` | Help screen |
| `y` / `n` | Confirm / cancel (ConfirmModal only) |

Footer shows the same hints (Textual auto-renders bindings).

---

## 11. Log System

- Log scopes: Overview (system), Sessions, Swarm event log, Swarm system log,
  and one per slot. `_log_msg(msg, slot_id=None)` writes to Overview + the
  active slot view; with `slot_id` it writes to that slot's view only.
- `_log_views` is keyed by `0` (overview), `-1` (swarm event log), the string
  `"swarm-system"` (swarm system log), and the int slot ids. `QwenTuiLogHandler`
  broadcasts each stdlib line into every registered view, so both Swarm panes
  receive the same stream and differ only in presentation.
- `QwenTuiLogHandler` streams stdlib logging into the RichLogs, filtered to
  app namespaces (`qwen`, `browser`, `modules`, `capabilities`, `agent`,
  `lifecycle`, `utility`, `shared`, `core`, `cli`, `surface`, root).
  Color by level: ERROR red, WARNING indigo, INFO cyan, DEBUG muted.
  Lines truncated at 200 chars.
- First paint deferred 0.4s (`set_timer`) to avoid overlay glitches.
- Log levels rendered with Rich markup: `bold` prefixes like `WARNING:`,
  `ERROR:`, `SWARM:`, `LOGIN RESULT:`.

---

## 12. Responsive / Layout Constraints (regression-locked)

- `#slots-table` `max-height: 4` rows — keeps System Event Log visible on
  terminals shorter than ~22 rows (PR #250).
- `#log-view-overview` fixed inside Overview pane; geometry asserted by
  `modules/cli/tests/unit_surface_cli_tui_app.py`.
- Left/right slot panes each `min-width: 30` cells; below that the layout
  degrades by horizontal clip.
- Metrics bar `overflow-x: auto` so long session text scrolls instead of
  wrapping.
- RichLogs all `wrap=True` — no horizontal overflow from long lines.

---

## 13. Empty / Error / Edge States

| State | Presentation |
| --- | --- |
| Fresh start | Overview log shows init messages; slot logs show `Set a prompt file, then press Enter or RUN.`; swarm table shows `No active swarm…`; metrics `ACTIVE: 0 DONE: 0 SESSION: CHECKING…`. |
| Slot already running | `WARNING: Slot N already running.` + toast. |
| Run cancelled >30s | ConfirmModal gate; worker-identity check prevents cancelling a successor run. |
| Quit with running jobs | `Confirm Quit` modal: "N automation job(s) are still running (Slots: …). Quitting will cancel them. Browser processes will be stopped." → `Quit and Cancel Jobs`. |
| Idle quit | Toast + log `Press Escape again within 2s to quit.` |
| Session expired | Badge `EXPIRED` (warn class); runs fail isolated per slot. |
| Session check hangs 15s | Badge `TIMEOUT` + warning toast advising `qwen-web-arwaky doctor`. |
| Swarm with no input | Toast `Select a file or folder before starting Swarm.` |
| Swarm ≥4 browsers | Resource-usage ConfirmModal before start. |
| Swarm system log empty, `Clear` pressed | `[Logs flushed by user]` written to `#log-view-swarm-system`. |
| Template sheet on a slot with no templates | `TEMPLATES: Slot N — 0 roles available (use the Quick Select dropdown to apply one).` |
| Log copy on empty buffer | `Log buffer is empty — nothing to copy.` |
| Template select of missing path | `WARNING: 'x' is not a known role and the file does not exist.` |

---

## 14. Visual Character Summary (for the redesign brief)

- Theme name: **Obsidian Terminal** — deep obsidian base (`#0f131c`), electric
  cyan accent (`#38bdf8`/`#8ed5ff`), emerald-green success (`#56e5a9`),
  layered surfaces (`#0a0e16` → `#1c2028` → `#181c24` → `#262a33` → `#31353e`).
- Style traits: 1px hairline borders; double accent borders on modals; muted
  uppercase section captions above content; card tiles with label+value pairs;
  height-3 rows as the vertical rhythm unit.
- Density: high — metric tiles, tables, and forms stacked with 1-row gaps.
- Hierarchy is color+weight driven (no size scale available in a TUI).
- Interaction signature: primary actions use filled cyan accent; destructive
  uses error-container red (`#93000a`); utility uses `📋`/`↻`/`🔄`.
