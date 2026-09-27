# Qwen Web Automation TUI — Current Text Design

Reference document for a redesign. Describes the TUI exactly as it exists
today: structure, every button, every label, colors, interactions, and
keyboard behavior. Source of truth: `modules/cli/src/surface_cli_tui_*.py`.

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

Vertical stack inside `.overview-container` (padding 1×2, scroll-y auto):

1. **Metric tile strip** (`.card-inner`, `bg_raised`, bordered, height 3)
   - `SLOTS` section-label + value `10` (metric-value).
   - `ACTIVE` section-label + value `0` (metric-accent, cyan — live count of
     RUNNING slots, debounced 4 refresh/sec).
   - `DONE` section-label + value `0` (metric-value — SUCCESS+FAILED count).
   - `SESSION` section-label + value badge (`#session-badge`), states:
     `CHECKING…` → `VALID` (green) / `EXPIRED` (warn class) / `TIMEOUT`
     (15s timeout) / `LOGGING IN…` / `N/A`.
2. **Label**: `Active Job Slots (1 Browser per Job)`
3. **Slots table** (`#slots-table`, DataTable, `bg_surface`, max-height 9
   rows so the log panel below stays visible on short terminals)
   - Columns: `Slot` | `Status` | `Prompt File` | `Duration`
   - One row per slot; status cell uses table format (section 8); duration
     ticks every 5s while running (`12s`, `1m 5s`).
4. **Pane title row**: `System Event Log` + button **`📋 Copy`**
   (`btn-copy-log`, 1-row height, accent text on `bg_base`).
5. **Log view** (`#log-view-overview`, RichLog, wrap, auto-scroll, 2000
   lines, bordered).
6. **Help hint** (dim): `Press ? for keyboard shortcuts. Configure a slot
   tab, then press Enter to run.`

Startup message in log: `Qwen Web Automation TUI initialized with multi-slot
architecture.` / `Each slot runs an independent Chromium process sharing
login state.`

---

## 4. Tab 2 — Sessions (`tab-sessions`)

1. **Metric tile strip** (`.card-inner`):
   - `REGISTERED` + value `0`
   - `HEALTHY` + value `0` (metric-ok, green)
   - `LIMITED` + value `0`
2. **Label**: `Registered Sessions`
3. **Sessions table** (`#sessions-table`): `ID` | `Name` | `Status` |
   `Last Used` | `Path`
4. **Button row** (`.toggle-row`, bordered, height 3):
   - **`🔄 Refresh`** — reloads the session pool into the table.
   - **`🔐 Add Session`** — primary accent button; opens SessionSetupScreen
     (currently falls back to a notify telling the user the CLI command).
   - **`🏥 Health Check`** — runs `SessionHealthChecker` on the pool,
     logs `HEALTH CHECK: n/m sessions healthy.`, refreshes table.
5. **Log view** (`#log-view-sessions`, 500 lines).

---

## 5. Tab 3 — Swarm (`tab-swarm`)

1. **Label**: `Attachment File or Folder` (section-label)
2. **Field row** (`.card-inner`): Input `#input-swarm-file` (placeholder
   `path/to/file or folder`) + button **`Browse`** (width 8) → opens
   FilePickerModal in directory-select mode.
3. **Action row** (`.card-inner`):
   - **`START`** — primary; validates input; if resource warning threshold
     reached (≥4 browsers) shows `ConfirmModal "Swarm Resource Usage"`
     first, then starts `swarm.start()`.
   - **`CANCEL`** — cancels the running swarm.
   - Label `Adaptive templates · max 10 browsers` (`#swarm-summary`;
     live updates to e.g. `COMPLETED · 8/10 completed · 1 failed · max 10
     browsers`).
4. **Swarm table** (`#swarm-table`): `Agent` | `Status` | `Attempt` |
   `Output`. Empty state row: `—` | `IDLE` | `—` | `No active swarm —
   select an attachment above and click START SWARM`.
5. **Pane title row**: `Swarm Log` + **`📋 Copy`** (`btn-copy-swarm-log`).
6. **Log view** (`#log-view-swarm`, 2000 lines).

Concurrency from env `QWEN_SWARM_CONCURRENCY` (default 10, clamped 1–10).

---

## 6. Tabs 4…N — Job Slots (`tab-slot-1` … `tab-slot-N`)

Each slot tab is a horizontal split:

```text
┌─ left-pane (48%, min 30 cols, bg_surface, right border, pad 1×2) ─┐
│  [ CONFIGURATION: SLOT N ]                     ← pane title       │
│  Prompt Template (Quick Select)               ← section-label     │
│  [Select: "Select a template or type file path below"]            │
│  Prompt File / Role (Required) *                                   │
│  [input path/to/prompt.md or role …]              [Browse]        │
│  Attachment File or Folder (Optional)                              │
│  [input path/to/file or folder]                   [Browse]        │
│  Output Destination                                                │
│  [input .qwen-web/output/…]                       [Browse]        │
│  ┌─ card-inner (headless toggle) ─────────────────────────────┐   │
│  │ Headless Browser                          [Switch ● on]     │   │
│  │ 1 independent browser in background                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  [ RUN IN SLOT N ]              ← primary, full width, height 3   │
│  [ Cancel Slot N ]              ← danger red, full width          │
│  [ ↻ Retry Slot N ]             ← indigo, hidden unless FAILED    │
├─ right-pane (52%, min 30 cols, bg_overlay, pad 1×2) ───────────────┤
│  [ LIVE LOG: BROWSER #N ]   [● READY]   [📋]   ← title + badge    │
│  (LoadingIndicator, hidden unless running)                         │
│  ┌─ slot log (RichLog, wrap, 2000 lines) ──────────────────────┐   │
│  │ Set a prompt file, then press Enter or RUN.    ← empty hint │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Slot form fields

| Field | Widget | Default / placeholder | Notes |
| --- | --- | --- | --- |
| Prompt Template | `Select` (dropdown) | blank; prompt `Select a template or type file path below` | Options = role templates from `modules/templates/*.md` (backend-engineer, business-analyst, devops-engineer, frontend-engineer, product-engineer, qa-engineer, security-engineer, software-architect, system-analyst, ui-ux-designer) with human titles. Selecting one fills the Prompt File input and logs `TEMPLATE: Slot N ← role 'x'`. Unknown path logs a WARNING. |
| Prompt File / Role (Required) `*` | `Input` + Browse | placeholder `path/to/prompt.md or role (any .md in modules/templates/)` | Manual edits desync the Select back to blank. |
| Attachment File or Folder (Optional) | `Input` + Browse | placeholder `path/to/file or folder` | Browse opens picker in directory mode. |
| Output Destination | `Input` + Browse | default `.qwen-web/output/` (DEFAULT_OUTPUT) | Browse opens picker in file mode. |
| Headless Browser | `Switch` (default ON) | subtext `1 independent browser in background` | |

### Slot action buttons (all full-width, height 3)

| Button | id | Style | Behavior |
| --- | --- | --- | --- |
| `RUN IN SLOT N` | `btn-run-N` | accent fill `fg_accent`/`fg_on_accent`, bold; hover inverts to outline | Validates inputs via resolver; starts worker; disabled state = already-running warning toast + log. Also bound to Enter/Ctrl+R. |
| `Cancel Slot N` | `btn-cancel-N` | `danger_bg` fill, `status_err` border, bold; hover inverts | <30s running: cancels immediately. >30s: `ConfirmModal "Cancel Slot"` ("Slot N has been running for Xs. Cancelling will lose the current progress."). Confirms only if same worker still owns the slot. Status goes CANCELLING → CANCELLED. |
| `↻ Retry Slot N` | `btn-retry-N` | `bg_raised` fill, `status_warn` text+border; hidden (`display: none`) | Shown only after FAILED; same handler as RUN. |

### Slot right pane

- Title: `[ LIVE LOG: BROWSER #N ]` (`fg_accent`, bold).
- Status badge (`#status-badge-N`, bold): shows live event badges
  (section 8) while running; terminal statuses otherwise.
- Copy button `📋` (icon-only, tooltip `Copy slot log`).
- `LoadingIndicator` visible only while the slot runs.
- Empty-state hint: `Set a prompt file, then press Enter or RUN.`

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
| 2 | `🔄 Refresh` | Sessions | `btn-sessions-refresh` | default |
| 3 | `🔐 Add Session` | Sessions | `btn-sessions-login` | primary (accent) |
| 4 | `🏥 Health Check` | Sessions | `btn-sessions-health` | default |
| 5 | `Browse` | Swarm file field | `btn-browse-swarm-file` | width 8, accent text |
| 6 | `START` | Swarm | `btn-swarm-start` | primary |
| 7 | `CANCEL` | Swarm | `btn-swarm-cancel` | default |
| 8 | `📋 Copy` | Swarm log title | `btn-copy-swarm-log` | default |
| 9 | `Browse` ×3 | Slot prompt/file/output fields | `btn-browse-{prompt,file,output}-N` | width 8 |
| 10 | `RUN IN SLOT N` | Slot left pane | `btn-run-N` | primary full-width |
| 11 | `Cancel Slot N` | Slot left pane | `btn-cancel-N` | danger full-width |
| 12 | `↻ Retry Slot N` | Slot left pane | `btn-retry-N` | warn, hidden until FAILED |
| 13 | `📋` | Slot log title | `btn-copy-log-N` | icon-only, tooltip |
| 14 | `Select This Folder` / `Cancel (Esc)` | File picker modal | `btn-select-folder` / `btn-cancel-modal` | primary / default |
| 15 | `Close` | Help modal | `help-close` | default |
| 16 | `Cancel` / confirm label | Confirm modal | `btn-cancel` / `btn-confirm` | default / error |
| 17 | `Delete Session & Login Again` / `Back to Main Menu` | Session setup | `login` / `back` | error / default |

Interactive non-button controls: slot `Select` dropdown, 4 inputs per slot
(template, prompt, attachment, output), swarm file input, headless `Switch`
per slot.

---

## 10. Keyboard Model

| Key | Action |
| --- | --- |
| `Alt+0` | Overview tab |
| `Alt+1…9` | Slot 1…9 |
| `Ctrl+Alt+0…9` | Slot 10…19 |
| `Ctrl+Alt+S` | Swarm tab |
| `Alt+Left` / `Alt+Right` | Prev / next slot tab |
| `Enter` / `Ctrl+R` | Run active slot |
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

- Log scopes: Overview (system), Sessions, Swarm, and one per slot.
  `_log_msg(msg, slot_id=None)` writes to Overview + the active slot view;
  with `slot_id` it writes to that slot's view only.
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
