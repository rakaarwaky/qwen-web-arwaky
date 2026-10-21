# DESIGN — Textual TUI Surface

> Visual and interaction contract for the Qwen terminal dashboard (`QwenTuiApp`).
> Audience: designers, surface engineers, TUI developers.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [BACKLOG.md](BACKLOG.md) (this surface).

The Obsidian Terminal theme is owned by the root [DESIGN.md](../../DESIGN.md);
this document binds that theme to the concrete Textual surface and defines the
component anatomy, interaction contract, and empty/error states of the TUI.
It never forks the shared palette, type scale, spacing unit, rounded ladder,
or elevation ladder — a TUI visual decision that cannot trace to a root
`DESIGN.md` token is out of contract. The terminal palette (the TUI-specific
projection of the shared theme) is canonical in `modules/tui/src/surface_tui_css_view.py`
(`_COLORS` / `THEME` / `SEMANTIC_ALIASES`); every hex below is mirrored from
that file and must change in the same commit.

## Brand & Style

### Kind

Smart surface (AES406). The TUI maps widget values and operator input onto
aggregate requests and renders the response; business semantics stay in the
orchestrators and adapters it calls. The dashboard is the primary visual
surface of the product: five in-app screens (Overview, Sessions, one Chat
console per slot, Swarm, Settings) plus modal pickers, toasts, and a docked
navigation bar.

### Color / Type Mapping

The TUI reads the theme through `THEME` in `surface_tui_css_view.py`. The root
[DESIGN.md](../../DESIGN.md) (Obsidian Terminal) defines the canonical color
roles; the TUI projects them onto terminal-safe tokens as follows. No raw hex
lives in a widget; every component references a token row.

| TUI token | Root `DESIGN.md` role | Usage |
|---|---|---|
| `bg` / `bg_base` | canvas (`$bg` / `#171A1F`) | screen background behind every panel |
| `surface` / `bg_raised` | surface / card | raised cards, table rows, slot chips |
| `bg_surface` | recessed strip | tab-bar and dock background |
| `border` | hairline | card and row separators |
| `accent` | primary accent (`#38BDF8`) | primary actions, focus ring, active tab, live beacon |
| `success` | diagnostic success | READY / DONE / ACTIVE state beacons |
| `warning` | diagnostic warning | LIMITED / EXPIRED / WARN notices |
| `danger` | diagnostic error | FAILED state, destructive confirm fills |
| `text` / `text_muted` | type roles | primary text / captions and placeholders |
| `label-*` type stops | one fixed type scale | panel titles `headline-*`, body `body-*`, badges and key hints `label-*` in JetBrains Mono |

Spacing multiplies from the root 4px base unit; every declared TUI value is an
integer multiple of it. Rounded and elevation ladders are the root ladders —
the TUI applies `0.25rem` to cards and chips, `0.5rem` to modal frames, and
layer elevation 0/1/2 to canvas, card, and modal surfaces respectively.

### Terminal Type Projection

The TUI cannot load the root design's Inter / JetBrains Mono web fonts, and a
terminal cell grid cannot honour `rem` / `px` sizes or `letter-spacing`, so
the root type stops are projected onto terminal **attributes** (weight, case,
width, emphasis) carried by Textual component classes. Each stop keeps its
role; only the rendering primitive changes.

| Root type stop | Terminal attribute projection | Example widgets |
|---|---|---|
| `headline-*` | bold, full-width single row, reverse-aware contrast | `.app-brand-title`, `.card-title` |
| `body-*` | default weight, wrapping flow (the only multi-row stop) | `QwenTuiRichLog` stream, `.override-purpose` |
| `label-*` | bold, uppercase or muted single row, no wrap | `.session-cell-status`, metric tile labels |

## Components

### Layout Regions

The app screen is one `TabbedContent` plus one docked footer. Regions, in
paint order:

| Region | Contents |
|---|---|
| Brand row (in-page, every screen) | `>_ QWEN-CLI` title + package version label; replaces a docked Header |
| `TabbedContent` | panes: Overview, Sessions, Slot 1…N (one Chat console each), Swarm, Settings |
| Overview screen | telemetry banner (ACTIVE ACCOUNTS + routed MODEL tiles), swarm status card, session-pool card, streaming log card |
| Sessions screen | session-pool card with metric tiles, one row per account, key-hint strip (`.session-key-hint`) under the table, and Add / Refresh / Edit / Delete actions |
| Chat screen (per slot) | brand row, slot-carousel pill row, telemetry header (live badge, beacon), event-log card, action pills (Prompt, Attach, Templates, Headless toggle), composer input with send trigger |
| Swarm screen | attachment card (file + Browse chip), output-inspection caption, swarm log card, Run / Stop / Restart deck — the primary CTA reads `▶ START` cold and flips to `↻ RESTART` once a run registers |
| Settings screen | runtime-override card: one row per registered environment value with Apply / Reset |
| Nav dock (docked footer) | icon + caption cells per screen, key-hint line, always visible |

The session-row action buttons render the documented glyphs `↻` / `☐` / `×`
for Refresh / Health / Delete with ASCII fallbacks `r` / `h` / `x`, and no
emoji in the session-row spec (UX-2-001). The shipped labels come from
`_GLYPHS` in
[modules/tui/src/surface_tui_utils_component.py](src/surface_tui_utils_component.py),
the documented iconography source of truth. The wide set renders only when
the terminal is not on a forced-ASCII locale (`_unicode_ok`): `C` / `POSIX`
fall back to the ASCII labels, while a UTF-8 locale keeps the wide glyphs
even under `NO_COLOR=1`.

### Cards (screen-card)

| Field | Role |
|---|---|
| card title | one-line screen-card headline (`screen-card-title`, `label-*` stop) |
| metric tiles | raised stat tiles inside the card (label + value + unit) |
| body rows | one per item (session, slot, override); a row owns its status beacon |
| action cluster | trailing buttons or pills; each pill/trigger maps to a token row |
| state layer | success / warning / danger beacon or muted placeholder when empty |

### Toasts / Notifications

Textual `notify()` toasts anchor in the toast region above the nav dock.

| Variant | Trigger | Semantics |
|---|---|---|
| information | run admitted, log copied, workspace initialized, quit hint | neutral, `accent`-family border, self-dismiss |
| error | empty session name, failed run envelope | `danger` border; the envelope hint stays visible in the slot's event log |

Toasts never block input; they must not move a focused widget or reparent a
modal's `ToastRack`. Clicks that land on a visible toast are guarded so text
selection does not crash the frame.

### Pickers (modal screens)

| Modal | Contract |
|---|---|
| `FilePickerModal` | file/folder selection; resolves to a path or `None` on dismiss; mouse-down on a visible toast is a no-op for selection |
| `TemplatePickerModal` | role template picker; selection loads the full template body into the active slot composer |
| `AddSessionModal` | session name entry; empty name is rejected with an error toast |
| `ConfirmModal` | destructive-action confirmation; `danger` fill on confirm, elevation layer 2 |
| `HelpScreen` | keybinding reference; dismissible, no state |

### Navigation & Tab Bar

| Level | Role | States |
|---|---|---|
| `TabbedContent` tab strip | switch screens: Overview / Sessions / Slots / Swarm / Settings | default / active / focus |
| Slot carousel (Chat screen) | one pill per job slot; the pane's own slot renders active | default / active / hover |
| Nav dock (footer) | icon + caption per screen with key hints; the TUI's persistent orientation bar | default / hover / focus |

### Chat Tab (per-slot console)

| Field | Role |
|---|---|
| slot-carousel pill row | jump between slot consoles; this pane's slot is filled |
| telemetry header | slot status badge, live beacon |
| event-log card | prompt echo, streaming pipeline events, and the response text |
| event-log card | slot event stream with timestamp; copy-to-clipboard action |
| action pill row | Prompt, Attach, Templates, Headless toggle |
| composer | input + send trigger; send dispatches the slot's run |

### Interaction Contract

#### Keyboard

Global bindings (from `QwenTuiApp.BINDINGS`):

| Keys | Action |
|---|---|
| `alt+0` / `alt+1..9` | switch to Overview / Slot 1–9 |
| `ctrl+alt+0..9` | switch to Slot 10–19 |
| `alt+left` / `alt+right` | previous / next slot tab |
| `ctrl+alt+s` / `ctrl+comma` | switch to Swarm / Settings |
| `enter` / `ctrl+r` | run the active slot |
| `ctrl+x` / `ctrl+c` | cancel the active slot / copy its log |
| `ctrl+l` / `ctrl+i` | login / init actions |
| `ctrl+q` / `escape` | quit (escape again within 2s confirms, via information toast) |
| `?` | help screen |
| `up` / `down` | Sessions tab row navigation |
| `a` | add a session — global, works on every screen |
| `r` / `e` / `d` | Sessions-pane-gated refresh / health / delete (`_sessions_active()`); no-ops off the Sessions tab |

#### Focus

- One focused widget at a time; the focus ring is the `accent` token.
- Modals capture focus on open and restore the previous focus on close.
- Input fields: default / hover / focus / disabled / filled / error states.

#### Empty and Error States

| State | Where | Rendering |
|---|---|---|
| No sessions | Sessions card | `session-empty` placeholder row |
| Idle slot | Chat console | composer placeholder (empty-state guidance), badge `● READY` |
| No swarm file attached | Swarm card | `swarm-file-name` reads "No file attached" |
| Run failed | Chat event log | `danger`-token error envelope with hint; badge `FAILED` |
| Session expired | Sessions / Chat | `warning`-token EXPIRED badge; destructive re-login from the action menu |

## Reference

- **Condition**: see [BACKLOG.md](BACKLOG.md).
- **Architecture**: [ARCHITECTURE.md](../../ARCHITECTURE.md) owns layer boundaries; this surface is `modules/tui/src/surface_tui_*`.
- **Glossary**:
  - **Slot**: one parallel run tracked in the dashboard; `NUM_SLOTS` panes render `Slot 1`…`Slot N`.
  - **Bead**: the `●` live marker on an active slot's tab label.
  - **Toast**: a Textual `notify()` message in the toast region; never blocks input.
