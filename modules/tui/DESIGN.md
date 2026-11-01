# DESIGN — Textual TUI Surface

## Design Overview

A smart surface (AES406) for the Qwen terminal dashboard (`QwenTuiApp`): it maps widget values and operator input onto aggregate requests and renders the response, while business semantics stay in the orchestrators and adapters it calls. The dashboard is the primary visual surface of the product — five in-app screens (Overview, Sessions, one Chat console per slot, Swarm, Settings) plus modal pickers, toasts, and a docked navigation bar. The Obsidian Terminal theme is owned by the root [DESIGN.md](../../DESIGN.md); a TUI visual decision that cannot trace to a root token is out of contract.

## Design Requirements

### DS-TUI-001: Color / Type Mapping

The TUI reads the theme through `THEME` in `modules/tui/src/surface_tui_css_view.py` (`_COLORS` / `THEME` / `SEMANTIC_ALIASES`) — the single source of truth for every hex. No raw hex lives in a widget; every component references a token row.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Canvas | Screen background behind every panel | `bg` / `bg_base` | `#171A1F` |
| Raised surface | Cards, table rows, slot chips | `surface` / `bg_raised` | `#22262C` |
| Recessed strip | Tab-bar and dock background | `bg_surface` | `#12151A` |
| Hairline | Card and row separators | `border` | `#2E343C` |
| Primary accent | Actions, focus ring, active tab, live beacon | `accent` | `#38BDF8` |
| Diagnostic success | READY / DONE / ACTIVE beacons | `success` | `#4ADE80` |
| Diagnostic warning | LIMITED / EXPIRED / WARN notices | `warning` | `#FACC15` |
| Diagnostic error | FAILED state, destructive confirm fills | `danger` | `#E5484D` |
| Type roles | Primary text / captions and placeholders | `text` / `text_muted` | `#E5E7EB` / `#9AA4B2` |

Spacing multiplies from the root 4px base unit; rounded and elevation ladders are the root ladders — the TUI applies `0.25rem` to cards and chips, `0.5rem` to modal frames, and layer elevation 0/1/2 to canvas, card, and modal surfaces.

### DS-TUI-002: Terminal Type Projection

The terminal cell grid cannot load Inter / JetBrains Mono web fonts or honour `rem` / `px` sizes, so the root type stops are projected onto terminal attributes (weight, case, width, emphasis) carried by Textual component classes. Each stop keeps its role; only the rendering primitive changes.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| `headline-*` | Bold, full-width single row, reverse-aware contrast | `.app-brand-title`, `.card-title` | panel/card titles |
| `body-*` | Default weight, wrapping flow (the only multi-row stop) | `QwenTuiRichLog` stream | event log, override purpose |
| `label-*` | Bold, uppercase or muted single row, no wrap | `.session-cell-status`, metric tiles | badges and key hints in JetBrains Mono |

### DS-TUI-003: Layout Regions

The app screen is one `TabbedContent` plus one docked footer.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Brand row | `>_ QWEN-CLI` title + package version label | in-page | replaces a docked Header |
| Overview | Telemetry banner, swarm status card, session-pool card, streaming log card | `TabbedContent` pane | telemetry + status |
| Sessions | Session-pool card, per-account rows, key-hint strip, action deck | `TabbedContent` pane | manage the pool |
| Chat (per slot) | Slot-carousel pills, telemetry header, event log, action pills, composer | `TabbedContent` pane | one console per slot |
| Swarm | Attachment card, log card, Run / Stop / Restart deck | `TabbedContent` pane | CTA `▶ START` → `↻ RESTART` |
| Settings | Runtime-override card with Apply / Reset rows | `TabbedContent` pane | env overrides |
| Nav dock | Icon + caption cells, key-hint line, always visible | docked footer | persistent orientation |

### DS-TUI-004: Session-Row Glyphs

Session-row action buttons render the documented glyphs for Refresh / Health / Delete with ASCII fallbacks; the shipped labels come from `_GLYPHS` in `modules/tui/src/surface_tui_utils_component.py`, the iconography source of truth.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Refresh / Health / Delete | Session-row actions | `↻` / `☐` / `×` | wide glyphs, no emoji (UX-2-001) |
| ASCII fallback | `C`, `POSIX`, or any locale containing `ascii` | `r` / `h` / `x` | `_unicode_ok` gate |
| Colour preference | `NO_COLOR=1` | wide glyphs retained | colour is gated, iconography is not |

### DS-TUI-005: Cards

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Card title | One-line screen-card headline | `screen-card-title` | `label-*` stop |
| Metric tiles | Raised stat tiles (label + value + unit) | raised tiles | inside the card |
| Body rows | One per item (session, slot, override) | row status beacon | each row owns its beacon |
| Action cluster | Trailing buttons or pills | token row per pill | each maps to a token |
| State layer | Beacon or muted placeholder when empty | success / warning / danger | empty-state rendering |

### DS-TUI-006: Toasts / Modals

Textual `notify()` toasts anchor in the toast region above the nav dock and never block input; clicks on a visible toast are guarded so selection does not crash the frame.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Information toast | Run admitted, log copied, workspace initialized, quit hint | `accent`-family border | self-dismiss, neutral |
| Error toast | Empty session name, failed run envelope | `danger` border | hint stays in the slot event log |
| `FilePickerModal` | File/folder selection | resolves to a path or `None` | dismiss-safe |
| `TemplatePickerModal` | Role template picker | loads the body into the active slot composer | |
| `AddSessionModal` | Session name entry | empty name rejected with an error toast | |
| `ConfirmModal` | Destructive-action confirmation | `danger` fill, elevation layer 2 | |
| `HelpScreen` | Keybinding reference | dismissible, no state | |

### DS-TUI-007: Keyboard and Focus

Global bindings from `QwenTuiApp.BINDINGS`; one focused widget at a time, the focus ring is the `accent` token, modals capture focus on open and restore it on close.

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Screen switch | `alt+0` / `alt+1..9`, `ctrl+alt+0..9` | Overview / Slot 1–9 / 10–19 | slot tabs |
| Slot nav | `alt+left` / `alt+right` | previous / next slot tab | |
| Surface switch | `ctrl+alt+s` / `ctrl+comma` | Swarm / Settings | |
| Run / cancel | `enter` / `ctrl+r`, `ctrl+x` / `ctrl+c` | run active slot / cancel + copy log | |
| Lifecycle | `ctrl+l` / `ctrl+i`, `ctrl+q` / `escape` | login / init, quit (escape again within 2s) | |
| Session actions | `a`, `r` / `e` / `d` | add; Sessions-pane-gated refresh / health / delete | `_sessions_active()` gate |

### DS-TUI-008: Empty and Error States

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| No sessions | Sessions card | `session-empty` placeholder row | |
| Idle slot | Chat console | composer placeholder, badge `● READY` | |
| No swarm file | Swarm card | `swarm-file-name` reads "No file attached" | |
| Run failed | Chat event log | `danger`-token envelope with hint, badge `FAILED` | |
| Session expired | Sessions / Chat | `warning`-token EXPIRED badge, re-login from the menu | |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](../../PRD.md) |
| Backlog | Task tracking, epics, and implementation status | [BACKLOG.md](BACKLOG.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
| Root Design | Obsidian Terminal theme (palette, type, spacing) | [DESIGN.md](../../DESIGN.md) |
