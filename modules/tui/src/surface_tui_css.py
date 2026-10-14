"""Obsidian Terminal design tokens and Textual CSS for the Qwen TUI application.

Surface layer (surface_cli): design-system colors and stylesheet string
consumed by :class:`~modules.tui.src.surface_tui_app.QwenTuiApp`.

This module is the **single source of truth for colour**. ``_COLORS`` is the
canonical palette; ``THEME`` and the ``$token`` CSS variables are derived from
it, so a component never hardcodes a hex value. The canonical hex values are
mirrored in the "Terminal Palette" table of
``design/obsidian_terminal/DESIGN.md`` — keep both in step when a value
changes.
"""

from __future__ import annotations

# V1/V4: single source of truth — derive THEME and CSS tokens from _COLORS.
# Every text colour below clears WCAG AA (4.5:1) against its background.
# Mirror the canonical hex values in design/obsidian_terminal/DESIGN.md.
_COLORS: dict[str, str] = {
    # ── Semantic surface stack (dark, layered) ──────────────────────────
    "bg": "#171A1F",  # canonical background / screen fill
    "surface": "#22262C",  # canonical raised surface (cards, rows)
    "bg_base": "#171A1F",  # alias: screen background
    "bg_surface": "#12151A",  # alias: recessed strip (tab bar)
    "bg_overlay": "#1C2026",  # alias: card fill
    "bg_raised": "#22262C",  # alias: raised tile / row hover target
    "bg_hover": "#2A2F36",  # surface hover
    "bg_active": "#31373F",  # surface pressed / selected row
    # ── Borders ─────────────────────────────────────────────────────────
    "border": "#2E343C",  # hairline separator
    "focus_ring": "#38BDF8",  # focus outline
    # ── Text ────────────────────────────────────────────────────────────
    "text": "#E5E7EB",  # canonical primary text
    "text_muted": "#9AA4B2",  # canonical secondary text
    "fg_primary": "#E5E7EB",  # alias: primary text
    "fg_muted": "#9AA4B2",  # alias: secondary text
    "fg_accent": "#7DD3FC",  # accent-tinted text
    "fg_on_accent": "#0B1220",  # text on accent fill
    "primary_fixed": "#BAE6FD",  # tinted monospace value
    # ── Accent / status ─────────────────────────────────────────────────
    "accent": "#38BDF8",  # primary accent
    "success": "#4ADE80",  # canonical success
    "status_ok": "#4ADE80",  # alias: success
    "bright": "#4ADE80",  # alias: success (highlight)
    "warning": "#FACC15",  # canonical warning
    "status_warn": "#FACC15",  # alias: warning
    "danger": "#E5484D",  # canonical danger
    "status_err": "#E5484D",  # alias: danger
    "status_info": "#38BDF8",  # informational = accent
    "status_muted": "#9AA4B2",  # neutral state
    # ── Danger surfaces ─────────────────────────────────────────────────
    # Subtle by default (tinted text on a dark red wash); the strong fill is
    # reserved for focus and the confirm modal.
    "danger_soft_bg": "#3A1214",
    "danger_soft_fg": "#FCA5A5",
    "danger_bg": "#E5484D",  # strong fill (focus / modal confirm)
    "danger_fg": "#FFF1F2",  # text on the strong fill
}

# Canonical semantic names (the design layer) → _COLORS key. Components and
# the design-token tests read the semantic layer through this map.
SEMANTIC_ALIASES: dict[str, str] = {
    "bg": "bg",
    "surface": "surface",
    "border": "border",
    "text": "text",
    "text-muted": "text_muted",
    "accent": "accent",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
}

THEME: dict[str, str] = {
    "accent": _COLORS["accent"],
    "accent_fg": _COLORS["fg_accent"],
    "primary": _COLORS["fg_primary"],
    "muted": _COLORS["fg_muted"],
    "ok": _COLORS["status_ok"],
    "warn": _COLORS["status_warn"],
    "err": _COLORS["status_err"],
    "info": _COLORS["status_info"],
    "bright": _COLORS["bright"],
    "danger": _COLORS["danger"],
    "success": _COLORS["success"],
    "warning": _COLORS["warning"],
}


def _css_vars() -> str:
    """V1: generate CSS variable declarations from the canonical color map."""
    return "\n".join(f" ${k}: {v};" for k, v in _COLORS.items())


# Build TUI_CSS via plain string concatenation (NOT f-string) to avoid ruff
# F821 false positives — ruff parses f-string interpolation as Python and
# flags CSS property names like ``background`` as undefined names. The body
# lives in its own constant so the assembly is name + name; a ``+`` directly
# against a triple-quoted literal makes bandit B608 read the CSS ``Select``
# rule plus a "from" in a comment as a hardcoded SQL query.
_CSS_HEADER = "/* ═══ Obsidian Terminal Design Tokens (V2 — auto-generated) ═══ */\n" + _css_vars()

_CSS_BODY = """

/* --- Base --------------------------------------------------------------- */
Screen {
    background: $bg_base;
    color: $fg_primary;
    layers: base modal;
}

/* --- In-page brand row (replaces the docked Header) ------------------------
   The mockups carry no top bar: `>_ QWEN-CLI` plus the `v6.5.2` chip sit as
   the first row inside the page canvas, on the surface color with no border
   below. Every screen yields this row as its first child, so the identity
   block is integrated into the page rather than docked above it. */
.app-brand-row {
    layout: horizontal;
    width: 100%;
    height: 1;
    background: $bg_base;
    align: left middle;
}

.app-brand-title {
    color: $fg_primary;
    text-style: bold;
    width: auto;
}

/* The mockup's version chip: a surface-container-high block with a hairline
   border. A one-row cell cannot carry a border, so the chip reads through its
   background alone. */
.app-brand-version {
    color: $status_muted;
    background: $bg_hover;
    width: auto;
    height: 1;
    margin-left: 1;
    padding: 0 1;
}

Footer {
    background: $accent;
    color: $fg_on_accent;
    height: 1;
    dock: bottom;
}

TabbedContent {
    height: 1fr;
    background: $bg_base;
}

Tabs {
    background: $bg_surface;
    border-bottom: solid $border;
    height: 3;
    overflow-x: auto;
    /* No tab strip in the mockups: navigation is via the bottom nav dock
       and the slot carousel inside the Chat pane. Hide the strip so slot
       tabs do not appear on Overview, Sessions, Swarm, or Settings. */
    display: none;
}

Tab {
    padding: 0 2;
    color: $fg_muted;
}

Tab.-active {
    color: $fg_primary;
    text-style: bold;
    background: $bg_active;
}

Underline {
    color: $accent;
}

/* --- Bottom nav dock (redesign v6.5.2) -------------------------------- */
/* The mockup's dock replaces the key-hint Footer: five equal cells spread
   across the full width, each stacking its icon above its caption, with the
   active cell carrying a short accent bar centred over its icon. dock: bottom
   takes the dock out of the flow, so it costs no layout rows and the Overview
   keeps its card/log geometry (tests/unit_tui_log_containment.py). */
.nav-dock {
    layout: vertical;
    height: auto;
    dock: bottom;
    background: $bg_surface;
    border-top: solid $border;
    padding: 0 1;
}

/* The five cells share one row so their 1fr widths line up with each other.
   Height is 6: each button is 2 content rows plus a 1px top and bottom
   border (4 total), so the row must reserve enough for the borders or
   Textual clips the label. */
.nav-items {
    layout: horizontal;
    width: 100%;
    height: 6;
}

/* One icon-over-label cell: the icon row sits above the caption. The button
   must be tall enough for both content rows plus its top/bottom border, so
   Textual reserves height 4 for the label and 2 for the borders. */
.nav-item {
    width: 1fr;
    min-width: 8;
    height: 4;
    padding: 0 2;
    background: $bg_surface;
    color: $fg_muted;
    text-style: bold;
    text-align: center;
    content-align: center middle;
}

/* Bigger, more tappable tab buttons (Problem: bottom-bar buttons too small):
   a subtle raised fill plus a hairline so each tab reads as a button, and a
   larger caption block so the icon + label fill the 2-row cell. */
.nav-item {
    background: $bg_overlay;
    border: solid $border;
}

.nav-item.nav-active {
    color: $fg_accent;
    background: $bg_active;
    border: solid $accent;
}

.nav-item.nav-inactive {
    color: $fg_muted;
}

.nav-item.nav-active:hover {
    background: $bg_active;
    color: $fg_accent;
    border: solid $accent;
}

.nav-item.nav-inactive:hover {
    background: $bg_hover;
    color: $fg_accent;
}

/* --- Obsidian Terminal card language ------------------------------------
   The redesign expresses the palette as nested surfaces: a screen canvas
   ($bg_base) holds rounded cards ($bg_overlay), which in turn hold the inner
   tiles ($bg_raised) that carry metric values. These three rules reproduce
   that layering with the borders the mockups use. */
.card {
    background: $bg_overlay;
    border: solid $border;
    padding: 1 2;
    margin-bottom: 1;
}

.card-inner {
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    height: 3;
    align: left middle;
}

/* Metric tile value inside a .card-inner: the large readout the mockups show
   (e.g. "3 Active", "Qwen3.8-Max"). The beacon dot is a separate Label. */
.metric-value {
    color: $fg_primary;
    text-style: bold;
    margin-right: 2;
}

/* Uppercase section label above a card, matching the mockup captions
   ("SWARM STATUS", "THREADS MATRIX", "OUTPUT INSPECTION"). */
.section-label {
    color: $fg_muted;
    text-style: bold;
    margin-bottom: 0;
}

/* Primary readout in cyan, used for values the mockups highlight: uptime,
   model name, streaming thread labels. */
.metric-accent {
    color: $fg_accent;
    text-style: bold;
}

/* Healthy / running value in the tertiary green. */
.metric-ok {
    color: $status_ok;
    text-style: bold;
}

/* Idle or dimmed tile (the mockups fade unused thread cells). */
.metric-dim {
    color: $fg_muted;
}

/* --- Overview Tab ------------------------------------------------------- */
.overview-container {
    height: 1fr;
    width: 100%;
    /* No bottom padding: the log strip sits directly above the dock's
       hairline, which buys the scroll band the row the THREADS MATRIX needs
       to show all five of its cell rows on a 42-row terminal. */
    padding: 1 2 0 2;
    background: $bg_base;
}

/* The engine cards + THREADS MATRIX live in this scroll band so the log
   strip below the band stays inside the tab pane at every terminal size. */
/* The Overview never scrolls: the mockup is a single screen, and the only
   scrollbar on it belongs to the log panel. `hidden` rather than `auto`
   because a scroll container sizes its 1fr children against the container
   instead of the rows the auto siblings leave over — which is what lets the
   log card fill the gap exactly. Below the size where the four blocks fit
   (about 36 rows) the band clips its last block instead of growing a
   scrollbar. */
.overview-scroll {
    width: 100%;
    height: 1fr;
    overflow-y: hidden;
    margin-bottom: 0;
}

/* Realtime System Log card: the mockup's bordered panel with a header row
   (live pips + LIVE STREAM) above the stream itself. It is the only 1fr child
   of the scroll band, so it takes every row the cards above it leave over and
   the stream reaches the nav dock instead of leaving a dead gap. min-height
   is the card's own content height (2 border + 2 padding + 2 header + 3 log
   rows), so a short terminal scrolls the band rather than flattening the
   panel. */
/* Compound selector: .screen-card is declared later in this file, so at equal
   specificity its `height: auto` would win and the card would size to its
   content instead of taking the rows the engine cards leave. */
.screen-card.log-card {
    height: 1fr;
    min-height: 9;
    background: $bg_surface;
    margin-bottom: 0;
}

/* Height 2 because Textual's height is border-box: the hairline takes one
   row and the header text the other. */
.log-card-head {
    layout: horizontal;
    width: 100%;
    height: 2;
    padding: 0 1;
    border-bottom: solid $border;
    align: left middle;
}

.log-pip {
    width: auto;
    margin-right: 1;
    text-style: bold;
}

.log-pip-live {
    color: $status_ok;
}

.log-pip-stream {
    color: $accent;
    margin-left: 2;
}

.log-card-title {
    width: auto;
    color: $fg_primary;
    text-style: bold;
}

.log-live-label {
    width: auto;
    color: $fg_muted;
}

.log-head-spacer {
    width: 1fr;
    height: 1;
}

/* The card carries the border, so the view only paints the stream rows. It
   fills the card's leftover height, and min-height 3 keeps the panel visible
   on a 20-row terminal (tests/unit_tui_log_containment.py). */
#log-view-overview {
    height: 1fr;
    min-height: 3;
    max-width: 100%;
    background: transparent;
    border: none;
    color: $fg_primary;
    padding: 0 1;
    overflow-x: hidden;
    overflow-y: auto;
}

.metrics-bar {
    layout: horizontal;
    height: auto;
    min-height: 3;
    background: $bg_surface;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
    overflow-x: auto;
}

.metric-item {
    margin-right: 3;
    color: $fg_primary;
    text-style: bold;
}

.template-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
}

/* --- Slot Pane Container ------------------------------------------------ */
.slot-container {
    height: 1fr;
    width: 100%;
    layout: horizontal;
    background: $bg_base;
}

.left-pane {
    width: 48%;
    min-width: 30;
    height: 100%;
    background: $bg_surface;
    border-right: solid $border;
    padding: 1 2;
}

.right-pane {
    width: 52%;
    min-width: 30;
    height: 100%;
    background: $bg_overlay;
    padding: 1 2;
}

.pane-title {
    background: $bg_base;
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
    border-bottom: solid $border;
    height: 3;
}

/* The Overview's log heading renders one line of text, so it uses a 1-row
   variant. .pane-title spends 3 rows on padding, which on a 20-row terminal
   pushed #log-view-overview one row past the bottom of the tab pane.
   The log fills remaining space below the card+table so it stays visible
   at every regression size. */
.pane-title-compact {
    background: $bg_base;
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 0;
    height: 1;
}

.field-label {
    color: $fg_primary;
    text-style: bold;
    margin-bottom: 0;
}

.field-row {
    layout: horizontal;
    height: 3;
    margin-bottom: 1;
}

.field-input {
    width: 1fr;
    background: $bg_raised;
    border: solid $border;
    color: $fg_primary;
}

.field-input:focus {
    border: solid $fg_accent;
}

/* Ten columns: the border and the default padding leave six for the label,
   which is exactly "Browse". At eight it wrapped into "Brow" / "se". */
.btn-browse {
    width: 10;
    min-width: 10;
    background: $bg_hover;
    color: $fg_accent;
    border: solid $border;
}

.btn-browse:hover {
    background: $bg_active;
    border: solid $fg_accent;
}

.toggle-row {
    layout: horizontal;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

/* The leading filler label spans the row so its trailing action sits flush
   right, as in the mockup. */
.toggle-row .field-label {
    width: 1fr;
}

.toggle-label-box {
    width: 1fr;
}

.toggle-subtext {
    color: $fg_muted;
}

Switch {
    background: $bg_active;
}

Switch.-on {
    background: $accent;
}

.btn-slot-run {
    width: 100%;
    height: 3;
    background: $fg_accent;
    color: $fg_on_accent;
    border: solid $fg_accent;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-run:hover {
    background: $bg_base;
    color: $fg_accent;
}

.btn-slot-cancel {
    width: 100%;
    height: 3;
    background: $danger_bg;
    color: $danger_fg;
    border: solid $status_err;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-cancel:hover {
    background: $bg_base;
    color: $status_err;
}

.slot-log-view {
    height: 1fr;
    max-width: 100%;
    background: $bg_base;
    border: solid $border;
    color: $fg_primary;
    padding: 1;
    overflow-x: hidden;
    overflow-y: auto;
}

.slot-loading {
    display: none;
    width: 1;
    height: 1;
    height: 1;
    margin-bottom: 1;
}

.status-badge {
    color: $status_ok;
    text-style: bold;
}

/* --- Modal File Picker -------------------------------------------------- */
FilePickerModal {
    align: center middle;
    background: rgba(15, 19, 28, 0.85);
}

#modal-container {
    width: 80%;
    height: 80%;
    background: $bg_surface;
    border: double $fg_accent;
    padding: 1 2;
}

/* Template picker modal: one button per discovered role, Cancel at the foot. */
#template-picker-container {
    width: 60%;
    height: auto;
    min-height: 8;
    background: $bg_surface;
    border: double $fg_accent;
    padding: 1 2;
}

#template-picker-title {
    background: $bg_base;
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid $border;
    height: 1;
    width: 100%;
    margin-bottom: 1;
}

#modal-title {
    background: $bg_base;
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid $border;
    height: 3;
    width: 100%;
}

#modal-tree {
    width: 100%;
    height: 1fr;
    background: $bg_base;
    border: solid $border;
    margin: 1 0;
    color: $fg_primary;
}

#modal-btn-row {
    height: 3;
    width: 100%;
    align: right middle;
    margin-top: 1;
}

#btn-cancel-modal {
    width: 16;
    background: $bg_hover;
    color: $fg_accent;
    border: solid $border;
}

#btn-cancel-modal:hover {
    background: $danger_bg;
    color: $danger_fg;
}

/* --- Prompt Template Select --------------------------------------------- */
Select {
    width: 1fr;
    background: $bg_raised;
    border: solid $border;
    color: $fg_primary;
    margin-bottom: 1;
}

Select:focus {
    border: solid $fg_accent;
}

/* Textual's SelectCurrent ships a `tall` border of its own, which painted
   ▔▔▔ / ▁▁▁ / ▎ inside the Select's own border. The Select already has one. */
SelectCurrent {
    border: none;
    background: transparent;
    padding: 0 1;
}

SelectOverlay {
    background: $bg_surface;
    border: solid $border;
    color: $fg_primary;
}

SelectOverlay > OptionList > .option-list--option-highlighted {
    background: $bg_active;
    color: $fg_accent;
}

/* --- Help Screen -------------------------------------------------------- */
HelpScreen {
    align: center middle;
    background: rgba(15, 19, 28, 0.9);
}

#help-container {
    width: 72;
    max-width: 90%;
    height: auto;
    max-height: 90%;
    background: $bg_surface;
    border: double $fg_accent;
    padding: 1 2;
}

#help-title {
    background: $bg_base;
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid $border;
    height: 3;
    width: 100%;
    margin-bottom: 1;
}

#help-body {
    color: $fg_primary;
}

#help-close {
    width: 16;
    margin-top: 1;
    background: $bg_hover;
    color: $fg_accent;
    border: solid $border;
}

.btn-slot-retry {
    display: none;
    width: 100%;
    height: 3;
    background: $bg_raised;
    color: $status_warn;
    border: solid $status_warn;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-retry:hover {
    background: $bg_base;
    color: $status_warn;
}

.btn-copy-log {
    width: auto;
    height: 1;
    margin-left: 1;
    background: $bg_raised;
    color: $fg_accent;
    /* Frameless: the card header is one row tall, so a border would leave the
       label no viewport at all. */
    border: none;
    padding: 0 1;
}

.btn-copy-log:hover {
    background: $bg_raised;
    color: $fg_accent;
}

/* --- Overview metric cards (redesign v6.5.2) ---------------------------- */
.overview-cards-row {
    layout: horizontal;
    width: 100%;
    margin-bottom: 1;
}

.overview-metric-card {
    background: $bg_overlay;
    border: solid $border;
    padding: 0 1;
    height: 3;
    align: left middle;
    min-width: 18;
    width: 1fr;
}

/* --- Swarm tab toggle buttons ------------------------------------------- */
.toggle-active {
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
    min-width: 12;
    height: 3;
}

.toggle-inactive {
    background: $bg_raised;
    color: $fg_primary;
    border: solid $border;
    min-width: 12;
    height: 3;
}

/* --- Headless mode pill button ------------------------------------------ */
.action-pill.action-pill-headless {
    background: $bg_overlay;
    color: $fg_primary;
    border: solid $border;
}

.action-pill.action-pill-headless.headless-on {
    background: $status_ok;
    color: $bg_base;
    text-style: bold;
}

.action-pill.action-pill-headless:hover {
    background: $status_ok;
    color: $bg_base;
}

.toggle-active:hover {
    background: $bg_active;
    color: $fg_accent;
}

.toggle-inactive:hover {
    background: $bg_hover;
    color: $fg_accent;
}

/* --- Template chip buttons in slot panes -------------------------------- */
.template-chip {
    min-width: 14;
    height: 3;
    padding: 0 1;
    background: $bg_raised;
    color: $fg_primary;
    border: solid $border;
    text-style: bold;
}

.template-chip:hover {
    background: $bg_hover;
    color: $fg_accent;
}

.template-chip.selected {
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
}

/* --- Swarm log header row ----------------------------------------------- */
.swarm-header-row {
    layout: horizontal;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

/* --- Redesign v6.5.2: engine status ring + cluster segments -------------- */
/* The mockups draw each engine readout as a ring gauge ("7/10") beside a
   label pair. A terminal cannot arc, so the ring collapses to a bold
   [ 7/10 ] badge and the arc is approximated by a 10-cell segment bar.
   Both engine cards (Swarm Status, Chat Status) fold into one bordered
   block (#overview-engine-card) so the readouts keep the same geometry on
   every terminal size.
   height: auto — never 1fr. The readouts are fixed-height content and the
   THREADS MATRIX below is the element that takes the free space, so a
   fractional height here would let the matrix's scrollable region starve
   the readouts to 0 on a 20-row terminal. */
/* Compound selector: .screen-card is declared later in this file, and equal
   specificity would let its padding win. The Overview cards drop the vertical
   padding so the mockup's title / readout / bar stack costs seven rows. */
.screen-card.engine-card {
    height: auto;
    padding: 0 2;
    margin-bottom: 1;
}

/* Card heading row: the mockup puts the section icon in a rounded chip on
   the left, then the heading beside it. The chip is roughly one text row tall
   in the mockup, so it is a padded accent glyph rather than a 3-row box —
   that keeps the whole card at the mockup's seven rows. */
.card-title-row {
    layout: horizontal;
    width: 100%;
    height: 1;
    padding: 0 1;
    align: left middle;
}

.card-icon {
    width: auto;
    height: 1;
    margin-right: 1;
    padding: 0 1;
    color: $accent;
    background: $bg_raised;
    text-style: bold;
}

.card-title {
    width: auto;
    height: 1;
    color: $fg_primary;
    text-style: bold;
}

/* The overview's counter row renders a single line of labels, so it takes one
   row rather than the 3-row .card-inner. The extra rows the mockup spends on
   card padding would otherwise push #log-view-overview below the fold on a
   20-row terminal, which tests/unit_tui_log_containment.py guards. The row is
   therefore unbordered — a border on a 1-row box would consume the row and
   leave the labels unpainted. The group reads as a card through its raised
   background. */
.engine-header-strip {
    layout: horizontal;
    width: 100%;
    height: 1;
    background: $bg_raised;
    padding: 0 1;
    margin: 0 0 1 0;
    align: left middle;
}

/* Label/value pairs read as separate words, so the label keeps a right margin
   instead of abutting the value that follows it. */
.engine-header-strip .section-label {
    color: $fg_muted;
    text-style: bold;
    margin-right: 1;
}

/* Header-strip dividers and idle readouts: kept dim so the accent values
   (active count, model, uptime) carry the eye. */
.metric-divider {
    color: $border;
    margin: 0 1;
}

.metric-value,
.metric-accent {
    margin-right: 1;
}

/* Right-aligned uptime readout pinned to the Swarm card's trailing edge,
   mirroring the mockup's stacked "Uptime Elapsed / 21m 53s". The label and
   its value share one Label; they split onto two lines only while a run is
   live, because tests pin the idle text ("Uptime Elapsed —"). A horizontal
   Textual container top-aligns its children (align only positions the group),
   so every readout fills the ring's three rows and centres its own text. */
.engine-uptime {
    color: $fg_muted;
    margin-left: 2;
    width: auto;
    height: 100%;
    content-align: right middle;
}

/* The mockup's telemetry bento: an inset surface-container panel holding the
   ring, its caption and the trailing uptime block. It is one row taller than
   a bare border would allow, so the panel is drawn with its own background
   instead of a border — the colour step is what makes it read as inset. */
.engine-bento {
    layout: horizontal;
    width: 100%;
    height: 3;
    margin: 0 1;
    background: $bg_raised;
    padding: 0 1;
    align: left middle;
}

/* Terminal ring: an arc cannot be drawn, so the gauge is a bordered box
   holding the same n/m count the mockup puts inside its circle. The count
   stays a single centred line, so the ring reads as a dial rather than a
   badge. */
.engine-ring {
    color: $accent;
    text-style: bold;
    background: $bg_raised;
    border: solid $accent;
    padding: 0 1;
    margin-right: 2;
    min-width: 7;
    width: auto;
    height: 3;
    text-align: center;
    content-align: center middle;
}

/* Dim sub-caption the mockup prints above a readout ("Active Threads"). */
.engine-sub {
    width: auto;
    height: 1;
    color: $fg_muted;
}

.engine-detail {
    color: $fg_muted;
    width: auto;
    height: 100%;
    content-align: left middle;
}

/* Two-line caption block (sub + detail) beside the chat status ring. It
   fills the readout so the pair hangs from the ring's top edge, which is
   how the mockup aligns its caption against the gauge. */
.engine-body {
    layout: vertical;
    width: auto;
    height: 100%;
    align: left middle;
}

.engine-body .engine-detail {
    height: 1;
}

/* Fills the space between a readout and the trailing uptime block. */
.engine-spacer {
    width: 1fr;
    height: 100%;
}

/* Cluster bar: one tinted segment per slot, stretched to the bar's own width
   so the strip reaches both card edges like the mockup's segment row. */
.cluster-bar {
    width: 100%;
    height: 1;
    margin-top: 0;
    padding: 0;
    color: $status_muted;
}

.cluster-seg-ok {
    color: $status_ok;
    text-style: bold;
}

.cluster-seg-run {
    color: $accent;
    text-style: bold;
}

.cluster-seg-done {
    color: $status_warn;
    text-style: bold;
}

.cluster-seg-idle {
    color: $status_muted;
}

.card-caption {
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    height: 1;
    margin-bottom: 0;
}

/* ═══ Mockup parity: LOGIN (session pool) ═══════════════════════════════ */
/* The mockup's SESSION POOL STATUS card holds three equal metric tiles and a
   full-width primary action, then one card per registered account. */

.screen-body {
    height: 1fr;
    width: 100%;
    padding: 1 2;
    background: $bg_base;
    overflow-y: auto;
}

/* Vertical's default is height: 1fr with overflow hidden, so a card would take
   an equal share of the pane and clip everything past its first rows. Cards
   size to their content and let .screen-body scroll instead. */
.screen-card {
    height: auto;
    background: $bg_overlay;
    border: solid $border;
    padding: 1 2;
    margin-bottom: 1;
}

.screen-card-title {
    color: $fg_muted;
    text-style: bold;
    width: 100%;
    margin-bottom: 1;
}

/* Mockup parity: the Overview telemetry card is two raised tiles — ACTIVE
   ACCOUNTS and MODEL — with the SLOTS / DONE / SESSION cluster tucked into
   the right tile's trailing edge. Each tile is two content rows (caption
   over value), and the tiles are split by a one-column gap that shows the
   card behind them. No vertical card padding: the tiles sit edge to edge so
   the banner stays four rows tall, as in the mockup. */
.screen-card.metric-card {
    padding: 0 2;
}

.metric-tiles {
    layout: horizontal;
    width: 100%;
    height: 2;
    margin-bottom: 0;
    align: left middle;
}

.metric-tile {
    layout: vertical;
    width: 1fr;
    height: 2;
    margin-right: 1;
    padding: 0 1;
    background: $bg_raised;
    align: left middle;
}

.metric-tile-label {
    width: auto;
    height: 1;
    color: $fg_muted;
    text-style: bold;
}

.metric-tile-value {
    layout: horizontal;
    width: auto;
    height: 1;
    align: left middle;
}

.metric-tile-number {
    width: auto;
    color: $fg_primary;
    text-style: bold;
    margin-right: 1;
}

.metric-tile-unit {
    width: auto;
    color: $fg_muted;
}

/* The model tile is the trailing one, so it carries no gap on its right. */
.metric-tile-model {
    margin-right: 0;
}

/* The mockup prints the routed model in primary-fixed, the one tinted
   monospace value in the banner. */
.metric-tile-model-value {
    color: $primary_fixed;
}

/* Three-up metric strip (REGISTERED / ACTIVE / LIMITED). The overview strip is
   a single row of label/value pairs, so it sizes to its content — a fixed
   height would add blank rows inside an already bordered card. The login grid
   stacks label over value inside a tile, so it overrides the height for two
   content rows. */
.login-metric-row {
    layout: horizontal;
    width: 100%;
    height: auto;
    margin-bottom: 0;
}

.login-metric-row.login-metric-grid {
    height: 4;
}

.login-metric-cell {
    layout: vertical;
    width: 1fr;
    height: 6;
    background: $surface;
    border: solid $border;
    border-right: none;
    padding: 1 1 0 1;
    margin-right: 1;
    content-align: left middle;
}

.login-metric-cell:last-child {
    border-right: solid $border;
}

.login-metric-label {
    color: $text_muted;
    text-style: bold;
    height: 1;
    width: auto;
}

.login-metric-value {
    color: $fg_accent;
    text-style: bold;
    height: 3;
    width: auto;
    content-align: left middle;
}

/* Contained ADD SESSION button at the top-right of the table panel (problem 5):
   a single 1-row slim call-to-action, not a full-width band. The spacer fills
   the left side so the button hugs the right edge. */
.session-add-row {
    layout: horizontal;
    width: 100%;
    height: 3;
    margin-bottom: 1;
    align: left middle;
}

.session-add-spacer {
    width: 1fr;
    height: 3;
}

.btn-session-add-contained {
    width: auto;
    min-width: 14;
    height: 3;
    background: $accent;
    color: $text;
    border: none;
    text-style: bold;
    padding: 0 2;
    content-align: center middle;
}

.btn-session-add-contained:hover {
    background: $fg_accent;
    color: $bg_base;
}

/* Full-width primary call-to-action ("ADD ACCOUNT"). Kept for other panes;
   the Sessions pane now uses the contained variant above. */
.btn-primary-full {
    width: 100%;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

.btn-primary-full:hover {
    background: $bg_base;
    color: $accent;
}

.btn-ghost {
    width: auto;
    height: 1;
    background: $bg_base;
    color: $fg_muted;
    border: none;
    padding: 0 1;
    text-style: bold;
}

.btn-ghost:hover {
    color: $fg_accent;
}

/* The session table: one static head row (NAME / STATUS / ACTIONS) and one
   row per account. Every row carries the same three cells plus the three
   action buttons, so the columns line up because the widths are fixed. */
/* The session table fills the pane's remaining height so there is no dead
   space below the last row: the card owns 1fr and the row list scrolls. */
#session-table {
    height: 1fr;
    min-height: 4;
}

#session-rows {
    height: 1fr;
    overflow-y: auto;
}

/* The empty-state line: informative, centred, muted. */
.session-empty {
    color: $text_muted;
    text-style: italic;
    padding: 2 1;
    width: 100%;
    content-align: center middle;
}

.session-row {
    layout: horizontal;
    width: 100%;
    height: 3;
    padding: 0 1;
    align: left middle;
}

/* Keyboard-first selection: a focused row gets the hover surface plus a 1px
   accent left edge, so the operator always sees which row the cursor is on. */
.session-row.session-row-selected {
    background: $bg_hover;
    border-left: solid $accent;
}

.session-row:focus-within {
    background: $bg_hover;
}

.session-row-head {
    background: $bg_active;
    border-bottom: solid $border;
}

.session-row .session-cell {
    height: 1;
    content-align: left middle;
}

.session-cell-name {
    width: 1fr;
    color: $fg_primary;
    text-style: bold;
}

.session-cell-status {
    width: 12;
    color: $fg_muted;
    text-style: bold;
}

.session-row-head .session-cell {
    color: $fg_accent;
    text-style: bold;
}

.session-cell-actions {
    width: 16;
    color: $fg_muted;
}

.session-cell.state-active {
    color: $status_ok;
}

.session-cell.state-limited {
    color: $status_err;
}

/* The row's three per-account action buttons: ↻ (refresh) reloads the pool
   from disk, 🧪 (health) runs the pool health check (same probe as
   'qwa session health'), 🗑 (trash) deletes the pool entry + profile (same
   logic as 'qwa session remove'). Icon-only, 4 cells wide. */
.account-btn {
    width: 4;
    min-width: 4;
    height: 2;
    border: none;
    background: $bg_hover;
    text-style: bold;
    content-align: center middle;
    margin-right: 1;
}

.account-btn-refresh {
    color: $fg_accent;
}

.account-btn-health {
    color: $accent;
}

/* Focus ring for every row action: a 1px accent outline so the keyboard
   cursor is visible on a button. */
.account-btn:focus {
    border: solid $focus_ring;
    background: $bg_active;
}

/* Delete is subtle by default — tinted text on a dark red wash — and only
   goes strong-red on focus, matching the confirm modal's danger fill. */
.account-btn-delete {
    color: $danger_soft_fg;
    background: $danger_soft_bg;
    margin-right: 0;
}

.account-btn-delete:focus {
    background: $danger_bg;
    color: $danger_fg;
}

.account-btn:hover {
    background: $bg_active;
}

/* ═══ Mockup parity: CHAT (slot console) ═══════════════════════════════ */

/* Horizontal slot picker: one pill per job slot, active one filled. */
/* The strip is a bare row of pills in the mockup, so it carries no frame of
   its own: a border here would eat the two rows the chips need and clip their
   labels out of the viewport. */
.slot-carousel {
    layout: horizontal;
    width: 100%;
    height: 3;
    background: $bg_surface;
    padding: 0 1;
    margin-bottom: 1;
    /* Hidden, not auto: the pills below size themselves to the terminal, so
       the carousel can never overflow and never grows a scrollbar. */
    overflow-x: hidden;
}

/* The pills split the width instead of sizing to their labels, so all ten
   slots fit whatever the terminal is. Textual's Button also ships
   min-width: 16, which alone pushed the last pills off the viewport. */
.slot-chip {
    width: 1fr;
    min-width: 0;
    height: 3;
    margin-right: 1;
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
    padding: 0;
    text-align: center;
}

.slot-chip.slot-chip-active {
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

/* Telemetry header: segmented Event/System log switch plus the live beacon.
   The switch sits on the left as in the mockup; an auto-width spacer carries
   the badge and beacon to the right edge. */
.telemetry-header {
    layout: horizontal;
    width: 100%;
    height: 3;
    align: left middle;
    margin-bottom: 1;
}

.telemetry-spacer {
    width: 1fr;
    height: 1;
}

/* Frameless: the two segments abut, so the container only supplies the
   backing colour. A border would leave the buttons a one-row viewport. */
.seg-switch {
    layout: horizontal;
    width: auto;
    height: 3;
    background: $bg_hover;
    margin-right: 1;
}

.seg-btn {
    width: auto;
    min-width: 12;
    height: 3;
    background: $bg_hover;
    color: $fg_muted;
    border: none;
    padding: 0 1;
    text-style: bold;
}

.seg-btn.seg-active {
    background: $accent;
    color: $fg_on_accent;
}

.live-beacon {
    color: $status_ok;
    text-style: bold;
    width: 1;
}

/* Chat transcript: user prompt on the right, agent response on the left.
   It sizes to its own content up to a cap instead of taking 1fr, so an idle
   slot hands its rows to the log card below instead of leaving a void. */
.chat-stream {
    width: 100%;
    height: auto;
    max-height: 12;
    background: $bg_base;
    padding: 1 2;
    overflow-y: auto;
}

.msg {
    width: 100%;
    margin-bottom: 1;
}

.msg-user {
    align-horizontal: right;
}

.msg-agent {
    align-horizontal: left;
}

.msg-author {
    color: $fg_accent;
    text-style: bold;
    width: 100%;
    margin-bottom: 0;
}

.msg-bubble {
    width: auto;
    max-width: 80%;
    height: auto;
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    color: $fg_primary;
}

.msg-bubble.msg-bubble-user {
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
}

.msg-chip {
    color: $fg_muted;
    background: $bg_active;
    text-style: bold;
    padding: 0 1;
}

.msg-time {
    color: $status_muted;
    width: 100%;
    margin-bottom: 0;
}

.msg-time.msg-time-user {
    text-align: right;
}

.msg-attach {
    width: auto;
    height: auto;
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
    padding: 0 1;
    margin-top: 0;
}

.code-block {
    width: 100%;
    height: 3;
    background: $bg_surface;
    border: solid $border;
    color: $fg_muted;
    padding: 0 1;
}

/* Action pills above the composer (Upload Prompt / Attach / Templates). */
.action-pill-row {
    layout: horizontal;
    width: 100%;
    height: 3;
    margin-bottom: 1;
}

.action-pill {
    width: auto;
    height: 3;
    background: $bg_raised;
    color: $fg_primary;
    border: solid $border;
    padding: 0 1;
    margin-right: 1;
    text-style: bold;
}

.action-pill-templates {
    background: $bg_hover;
    color: $fg_accent;
}

/* File indicator row: shows the attached file/folder, hidden by default. */
.file-indicator {
    width: 100%;
    height: 1;
    color: $fg_muted;
    text-style: bold;
    margin-bottom: 1;
}

/* Composer row: prompt glyph, free-text input, send button. */
.composer {
    layout: horizontal;
    width: 100%;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.composer-glyph {
    color: $fg_accent;
    text-style: bold;
    width: 2;
}

.composer-input {
    width: 1fr;
    background: $bg_raised;
    border: none;
    color: $fg_primary;
    height: 1;
}

.btn-send {
    width: 5;
    min-width: 5;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

/* The console shell: a vertical stack of carousel, telemetry header,
   transcript, log card, action pills, and composer. The transcript takes the
   slack (1fr) while the log card keeps a fixed block so a chatty run cannot
   squeeze the composer off the pane. */
.chat-screen {
    layout: vertical;
    width: 100%;
    height: 1fr;
    background: $bg_base;
    padding: 1 2;
}

.chat-hint {
    width: 100%;
    height: auto;
    color: $fg_muted;
    text-style: italic;
    text-align: center;
}

.msg-author.msg-author-right {
    text-align: right;
}

/* EVENT LOG [SLOT #N] card: header row, the buffer, and the trailing clock. */
/* The log card is the pane's 1fr child: it takes every row the carousel,
   header, transcript and composer leave, so the console always fills the
   screen exactly, and min-height 10 keeps the buffer readable when the
   terminal is short. */
.event-log-card {
    layout: vertical;
    width: 100%;
    height: 1fr;
    min-height: 4;
    background: $bg_overlay;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
}

/* One row, as the mockup draws it: title, slot tag and the Copy ghost share
   the header line, so the card's floor is 4 rows (2 border + header + clock)
   and the console still fits a 30-row terminal. */
.event-log-head {
    layout: horizontal;
    width: 100%;
    height: 1;
    align: left middle;
}

.event-log-title {
    width: auto;
    margin-right: 1;
    color: $fg_accent;
    text-style: bold;
}

.event-log-slot {
    width: 1fr;
    color: $status_ok;
    text-style: bold;
}

.slot-log-time {
    width: 100%;
    height: 1;
    text-align: left;
    color: $status_muted;
}

/* ═══ Mockup parity: SWARM (multi-agent stream) ═══════════════════════ */

/* The console shell, same as the chat console: attachment card, view toggle,
   log card, action deck. The log card is the only 1fr child, so the deck
   lands above the nav dock at every terminal height. */
.swarm-screen {
    layout: vertical;
    width: 100%;
    height: 1fr;
    background: $bg_base;
    padding: 1 2 0 2;
}

/* Attachment card: file icon, resolved filename, Browse chip. The chip is a
   one-row ghost — the default three-row Button overflowed this three-row card
   and rendered as an empty box with no label. */
.swarm-file-card {
    layout: horizontal;
    width: 100%;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    margin-bottom: 1;
    padding: 0 1;
    align: left middle;
}

.swarm-file-icon {
    color: $fg_accent;
    text-style: bold;
    width: auto;
    margin-right: 1;
}

.swarm-file-name {
    width: 1fr;
    color: $fg_primary;
    text-style: bold;
}

.swarm-browse-chip {
    width: auto;
    height: 1;
    min-width: 0;
    background: $bg_active;
    color: $fg_muted;
    border: none;
    padding: 0 1;
    text-style: bold;
}

.swarm-browse-chip:hover {
    color: $fg_accent;
}

.swarm-file-input {
    width: 1fr;
    height: 1;
    background: $bg_raised;
    border: solid $border;
    color: $fg_primary;
}

/* View toggle row: caption on the left, segmented switch on the right. The
   swarm switch is one row (the mockup's pill pair); the chat console keeps
   its taller switch under .telemetry-header. */
.output-inspection {
    layout: horizontal;
    width: 100%;
    height: 1;
    margin-bottom: 1;
    align: left middle;
}

.output-inspection .card-caption {
    width: 1fr;
    color: $status_muted;
    text-style: bold;
}

.swarm-seg {
    height: 1;
}

.swarm-seg .seg-btn {
    height: 1;
    min-width: 10;
}

/* Log card: the path header with its hairline, the stream, and the socket
   footer. Compound selector so .screen-card's padding cannot win over the
   1fr height the mockup gives the panel. */
.screen-card.swarm-log-card {
    height: 1fr;
    min-height: 8;
    background: $bg_surface;
    margin-bottom: 0;
}

.swarm-log-head {
    layout: horizontal;
    width: 100%;
    height: 2;
    align: left middle;
    border-bottom: solid $border;
}

.swarm-log-path {
    width: 1fr;
    height: 1;
    color: $status_muted;
    text-style: bold;
}

.swarm-clear-chip {
    width: auto;
    height: 1;
    min-width: 0;
    background: $bg_surface;
    color: $fg_muted;
    border: none;
    padding: 0 1;
    text-style: bold;
}

.swarm-clear-chip:hover {
    color: $status_err;
}

/* The card carries the frame, so the view only paints stream rows. */
.swarm-log-view {
    width: 100%;
    height: 1fr;
    max-width: 100%;
    background: transparent;
    border: none;
    color: $fg_primary;
    padding: 0;
    overflow-x: hidden;
    overflow-y: auto;
}

.swarm-log-foot {
    layout: horizontal;
    width: 100%;
    height: 1;
    align: left middle;
}

.swarm-caret {
    width: auto;
    color: $accent;
    text-style: bold;
    margin-right: 1;
}

/* Socket listener line under the stream. */
.listener-line {
    width: 1fr;
    height: 1;
    color: $fg_muted;
    text-style: italic;
}

/* ═══ SETTINGS (per-slot configuration) ═══════════════════════════════ */

/* Same shell as the chat and swarm consoles: brand row, slot carousel, and
   one card per slot with only the selected one displayed. */
.settings-screen {
    layout: vertical;
    width: 100%;
    height: 1fr;
    background: $bg_base;
    padding: 1 2 0 2;
}

/* Compound selector: .screen-card is declared later with `height: auto`, and
   at equal specificity that would stop the card from filling the pane. */
.screen-card.settings-card {
    height: 1fr;
    min-height: 26;
    background: $bg_overlay;
    margin-bottom: 0;
}

/* Uppercase field captions, the mockup's label treatment. */
.settings-caption {
    width: auto;
    height: 1;
    color: $status_muted;
    text-style: bold;
}

/* Quick-select chips share one row; a long template list is clipped rather
   than growing the card. */
.settings-chips {
    layout: horizontal;
    width: 100%;
    height: 1;
    margin-bottom: 1;
    overflow-x: hidden;
}

/* Frameless: a one-row chip cannot carry a border — the border would eat the
   row and the label would vanish (that is what the empty boxes were). */
.settings-chips .template-chip {
    height: 1;
    min-width: 0;
    padding: 0 1;
    margin-right: 1;
    border: none;
    background: $bg_raised;
}

/* Headless row: caption, subtext, switch on the trailing edge. */
.settings-toggle {
    layout: horizontal;
    width: 100%;
    /* Three rows: Textual's Switch is a three-row control, and squeezed into
       one row it rendered as a bare ▊ ▔▔▔ stub. */
    height: 3;
    align: left middle;
    margin-bottom: 1;
}

.settings-toggle .settings-caption {
    width: auto;
    height: 3;
    content-align: left middle;
}

.settings-toggle .toggle-subtext {
    width: auto;
    height: 3;
    content-align: left middle;
    margin-left: 1;
}

.settings-toggle-spacer {
    width: 1fr;
    height: 3;
}

/* Section switch alone on its row. An earlier draft put the storage path in a
   trailing hint here and it truncated mid-word on any terminal under ~130
   columns; the path belongs with the overrides, which is where it means
   something, and that card is 140 columns wide. */
.settings-switch {
    height: 3;
    margin-bottom: 1;
}

.settings-toggle Switch {
    width: 4;
    height: 3;
}

/* Run controls on the card's last row: the primary takes half, the other two
   share the rest, so nothing hides below the fold. */
.settings-actions {
    layout: horizontal;
    width: 100%;
    height: 3;
}

/* margin-top: 0 — the slot buttons carry a one-row top margin for the old
   stacked form, and inside this row it pushed each button down a row. */
.settings-actions .btn-slot-run {
    width: 2fr;
    height: 3;
    margin-top: 0;
}

.settings-actions .btn-slot-cancel,
.settings-actions .btn-slot-retry {
    width: 1fr;
    height: 3;
    margin-top: 0;
    margin-left: 1;
}

/* ═══ SETTINGS (runtime overrides) ═══════════════════════════════════ */

/* The registry is 18 values, which cannot fit one screen. The card scrolls
   inside its own band rather than growing the pane — the nav dock and the
   section switch must stay put. */
.override-scroll {
    width: 100%;
    height: 1fr;
}

/* Compound selector: `.screen-card.settings-card` earlier in this file is also
   two classes deep and would pin the card to the pane height, which leaves the
   scroll container nothing to scroll. */
.screen-card.override-card {
    height: auto;
    margin-bottom: 0;
}

.override-blurb {
    height: 1;
    color: $status_muted;
    margin-bottom: 1;
}

/* Where an applied value is stored. Its own row inside the card rather than a
   trailing hint on the section switch, which had no room for it. */
.override-hint {
    height: 1;
    color: $status_muted;
    text-style: italic;
}

/* Seven rows: name+badge, purpose, three-row field, the hairline's padding,
   then the hairline. The row's declared height is its border box, so it has to
   cover the padding too or the field is clipped and shows no value. */
.override-row {
    width: 100%;
    height: 7;
    margin-bottom: 1;
    padding-bottom: 1;
    border-bottom: solid $border;
}

.override-head {
    width: 100%;
    height: 1;
}

.override-name {
    width: auto;
    height: 1;
    color: $fg_primary;
    text-style: bold;
}

/* Three states: default, in force now, stored but needing a restart. */
.override-badge {
    width: 1fr;
    height: 1;
    content-align: right middle;
    color: $status_muted;
}

.override-badge-active {
    color: $status_ok;
    text-style: bold;
}

.override-badge-restart {
    color: $status_warn;
}

.override-purpose {
    width: 100%;
    height: 1;
    color: $status_muted;
    text-overflow: ellipsis;
}

.override-field-row {
    width: 100%;
    height: 3;
}

/* Same treatment as the slot form's fields: an explicit frame, because the
   default Input chrome collapses to a bare rule at this card's padding. */
.override-input {
    width: 1fr;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    color: $fg_primary;
}

.override-input:focus {
    border: solid $fg_accent;
}

/* Apply/Reset are the same width as the Browse chip on the form above, so the
   two halves of the Settings screen line up. */
.btn-apply {
    width: 10;
    min-width: 10;
    height: 3;
    margin: 0 0 0 1;
    background: $bg_hover;
    color: $fg_accent;
    border: solid $border;
}

/* Reset is a quiet affordance: it removes an override, so it must not look
   like the action that writes one. */
.btn-reset {
    color: $status_muted;
}

/* Stop / Restart action deck under the log card. */
.swarm-action-deck {
    layout: horizontal;
    width: 100%;
    height: 3;
    margin-top: 1;
}

.btn-stop {
    width: 1fr;
    height: 3;
    background: $bg_raised;
    color: $status_err;
    border: solid $border;
    text-style: bold;
}

/* Headless toggle in the swarm action deck. */
.swarm-headless-toggle {
    width: 1fr;
    height: 3;
    background: $bg_raised;
    color: $status_ok;
    border: solid $status_ok;
    text-style: bold;
}

.swarm-headless-toggle:hover {
    background: $bg_hover;
    color: $status_ok;
}

.btn-restart {
    width: 2fr;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

/* ═══ SYSTEM ACTIONS CARD (Settings pane) ═══════════════════════════ */

/* The Settings pane is the runtime-override surface: a single scrolling
   card. Doctor and update stay reachable through their own commands. */
.screen-card.system-actions-card {
    height: auto;
    margin-bottom: 1;
}

.btn-doctor {
    width: auto;
    height: 3;
    background: $bg_raised;
    color: $status_ok;
    border: solid $status_ok;
    text-style: bold;
    margin-right: 1;
}

.btn-update {
    width: auto;
    height: 3;
    background: $bg_raised;
    color: $fg_accent;
    border: solid $border;
    text-style: bold;
    margin-right: 1;
}
"""

TUI_CSS = _CSS_HEADER + _CSS_BODY

__all__ = ["THEME", "TUI_CSS"]
