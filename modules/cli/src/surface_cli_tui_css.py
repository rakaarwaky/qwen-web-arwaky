"""Obsidian Terminal design tokens and Textual CSS for the Qwen TUI application.

Surface layer (surface_cli): design-system colors and stylesheet string
consumed by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.

Token names and hex values derive from the canonical material-spec map in
``design/obsidian_terminal/DESIGN.md`` (the "Obsidian Terminal" system
released with the Obsidian Terminal redesign PR #467).
"""

from __future__ import annotations

# V1/V4: single source of truth — derive THEME and CSS tokens from _COLORS.
# All hex values must match the "Obsidian Terminal" material palette in
# design/obsidian_terminal/DESIGN.md, lines 4-64.  Do not hand-edit a
# value without re-generating from that source file first.
_COLORS: dict[str, str] = {
    # Obsidian Terminal surface stack
    "fg_accent": "#8ed5ff",  # primary
    "fg_primary": "#dfe2ee",  # on-surface
    "fg_muted": "#bdc8d1",  # on-surface-variant
    "fg_on_accent": "#00354a",  # on-primary
    "accent": "#38bdf8",  # primary-container
    "bg_base": "#0f131c",  # surface / background
    "bg_surface": "#0a0e16",  # surface-container-lowest
    "bg_raised": "#1c2028",  # surface-container
    "bg_overlay": "#181c24",  # surface-container-low
    "bg_hover": "#262a33",  # surface-container-high
    "bg_active": "#31353e",  # surface-container-highest
    "border": "#3e484f",  # outline-variant
    # Status colors (mapped from material error/tertiary/primary tokens)
    "status_ok": "#56e5a9",  # tertiary
    "status_warn": "#c0c1ff",  # secondary (amber replaced by indigo to fit palette)
    "status_err": "#ffb4ab",  # error
    "status_info": "#38bdf8",  # primary-container
    "status_muted": "#87929a",  # outline
    "bright": "#56e5a9",  # tertiary (was #4ADE80, now matches "ok")
    # V2: danger tokens — uses error-container / on-error-container
    "danger_bg": "#93000a",
    "danger_fg": "#ffdad6",
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
}


def _css_vars() -> str:
    """V1: generate CSS variable declarations from the canonical color map."""
    return "\n".join(f" ${k}: {v};" for k, v in _COLORS.items())


# Build TUI_CSS via plain string concatenation (NOT f-string) to avoid ruff
# F821 false positives — ruff parses f-string interpolation as Python and
# flags CSS property names like ``background`` as undefined names.
_CSS_HEADER = "/* ═══ Obsidian Terminal Design Tokens (V2 — auto-generated) ═══ */\n" + _css_vars()

TUI_CSS = (
    _CSS_HEADER
    + """

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

.app-brand-version {
    color: $status_muted;
    background: $bg_hover;
    width: auto;
    height: 1;
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
/* The mockup's dock replaces the key-hint Footer: same single row at the
   bottom of the screen, but carrying the four section names with the active
   one underlined. dock: bottom takes it out of the flow, so it costs no
   layout rows and the Overview keeps its table/log geometry
   (tests/unit_tui_log_containment.py). */
.nav-dock {
    layout: horizontal;
    height: 4;
    dock: bottom;
    background: $bg_surface;
    border-top: solid $border;
    padding: 0 1;
    align: center middle;
}

.nav-item {
    min-width: 12;
    height: 3;
    padding: 0 1;
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
    text-style: bold;
}

/* Active tab: cyan hairline across its top edge and an accent label, the
   marker the mockup draws above the current screen. */
.nav-item.nav-active {
    background: $bg_active;
    color: $fg_accent;
    border-top: solid $accent;
    border-bottom: none;
}

.nav-item.nav-inactive {
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
}

.nav-item.nav-active:hover {
    background: $bg_active;
    color: $fg_accent;
}

.nav-item.nav-inactive:hover {
    background: $bg_hover;
    color: $fg_accent;
}

/* Trailing keyboard hint inside the dock, replacing the key list the old
   Footer rendered. */
.nav-hint {
    color: $fg_muted;
    margin-left: 2;
    width: auto;
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
    padding: 1 2;
    background: $bg_base;
}

/* The engine cards + THREADS MATRIX live in this scroll band so the log
   strip below the band stays inside the tab pane at every terminal size. */
.overview-scroll {
    width: 100%;
    height: 1fr;
    overflow-y: auto;
    margin-bottom: 1;
}

#log-view-overview {
    height: 4;
    min-height: 3;
    max-width: 100%;
    background: $bg_base;
    border: solid $border;
    color: $fg_primary;
    padding: 1;
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

/* The Overview's slot table lives below the THREADS MATRIX. It carries the
   per-slot prompt file and exact pipeline status that the matrix's one-word
   state does not. Fixed height = 5 (1 header + 4 data rows) so its content
   actually renders instead of collapsing to a header-only band — see tests
   for the regression lock that the log panel must remain visible at every
   terminal size. */
#slots-table {
    height: 5;
    background: $bg_surface;
    border: solid $border;
    margin-bottom: 1;
    overflow-y: scroll;
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

.btn-browse {
    width: 8;
    min-width: 8;
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
    height: 1;
    margin-bottom: 1;
}

.status-badge {
    color: $status_ok;
    text-style: bold;
}

#session-badge {
    color: $status_ok;
    text-style: bold;
    background: $bg_raised;
    padding: 0 1;
}

#session-badge.invalid {
    color: $status_warn;
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
.engine-card {
    height: auto;
    margin-bottom: 1;
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
   mirroring the mockup's "Uptime Elapsed 21m 53s". */
.engine-uptime {
    color: $fg_muted;
    margin-left: 2;
}

.engine-readout {
    layout: horizontal;
    width: 100%;
    height: 1;
    padding: 0 1;
    margin: 0;
    align: left middle;
}

.engine-ring {
    color: $accent;
    text-style: bold;
    background: $bg_raised;
    padding: 0 1;
    margin-right: 2;
    min-width: 7;
    width: auto;
}

.engine-name {
    color: $fg_primary;
    text-style: bold;
    margin-right: 2;
    width: auto;
}

.engine-detail {
    color: $fg_muted;
    width: 1fr;
}

/* Cluster bar: one character per slot, coloured by that slot's state. */
.cluster-bar {
    width: 100%;
    height: 1;
    padding: 0 1;
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

/* Threads Matrix: the mockup renders a 2-column grid of numbered cells
   (01 Streaming 4m12s). A DataTable keeps the same information readable in a
   fixed-width terminal while preserving its selectable rows. Height 1fr so
   it fills the free space between the readouts card above and the two pinned
   bands below; it scrolls when terminals are too short for every row to fit. */
#threads-matrix {
    height: 1fr;
    background: $bg_surface;
    border: solid $border;
    margin-bottom: 1;
}

.card-caption {
    color: $fg_accent;
    text-style: bold;
    padding: 0 1;
    height: 1;
    margin-bottom: 0;
}

.btn-sessions-refresh,
.btn-sessions-login,
.btn-sessions-health {
    /* Ghost geometry: these ride in a 1-row .toggle-row, and a default 3-row
       Button overflows that single content line and renders as a clipped fill
       with no label. */
    width: auto;
    height: 1;
    min-width: 12;
    padding: 0 1;
    margin-right: 1;
    background: $bg_raised;
    color: $fg_primary;
    border: none;
    text-style: bold;
}

.btn-sessions-refresh:hover,
.btn-sessions-health:hover {
    background: $bg_hover;
    color: $fg_accent;
}

.btn-sessions-login {
    background: $accent;
    color: $fg_on_accent;
    border: none;
}

.btn-sessions-login:hover {
    background: $bg_base;
    color: $accent;
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
    width: 1fr;
    height: 4;
    background: $bg_raised;
    border: solid $border;
    padding: 0 1;
    margin-right: 1;
}

.login-metric-label {
    color: $fg_muted;
    text-style: bold;
}

.login-metric-value {
    color: $fg_accent;
    text-style: bold;
}

/* Full-width primary call-to-action ("ADD ACCOUNT"). */
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

/* One account card: identity on top, hairline telemetry row underneath with
   the health state and the two per-account actions (mockup Login). */
.account-card {
    layout: vertical;
    width: 100%;
    height: auto;
    background: $bg_raised;
    border: solid $border;
    margin-bottom: 1;
}

.account-card-head {
    layout: horizontal;
    width: 100%;
    height: 3;
    padding: 0 1;
    align: left middle;
}

.account-card-foot {
    layout: horizontal;
    width: 100%;
    height: 3;
    padding: 0 1;
    border-top: solid $border;
    align: left middle;
}

.account-avatar {
    width: 3;
    height: 3;
    content-align: center middle;
    background: $bg_active;
    color: $fg_accent;
    text-style: bold;
    margin-right: 1;
}

.account-email {
    width: 1fr;
    color: $fg_primary;
    text-style: bold;
}

.account-status {
    width: 1fr;
    text-style: bold;
    margin-right: 1;
}

.account-status.state-active {
    color: $status_ok;
}

.account-status.state-limited {
    color: $status_err;
}

.account-btn {
    width: 6;
    min-width: 6;
    height: 2;
    border: none;
    background: $bg_hover;
    text-style: bold;
}

.account-btn-test {
    color: $accent;
    margin-right: 1;
}

.account-btn-disconnect {
    color: $status_err;
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
    overflow-x: auto;
}

/* Width follows the label so all ten pills fit one row at a normal terminal
   width; a fixed min-width pushed SLOT 10 out under the scroll bar. */
.slot-chip {
    width: auto;
    /* Textual's Button ships min-width: 16, which is wide enough to push the
       last pills of the carousel past the viewport; override it. */
    min-width: 0;
    height: 3;
    margin-right: 1;
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
    padding: 0;
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

/* Chat transcript: user prompt on the right, agent response on the left. */
.chat-stream {
    width: 100%;
    height: 1fr;
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
.event-log-card {
    layout: vertical;
    width: 100%;
    height: 10;
    background: $bg_overlay;
    border: solid $border;
    padding: 0 1;
    margin-top: 1;
    margin-bottom: 1;
}

.event-log-head {
    layout: horizontal;
    width: 100%;
    height: 3;
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

/* Settings: one configuration block per slot, only the chosen one shown. */
.slot-config {
    width: 100%;
    height: auto;
    background: $bg_overlay;
    border: solid $border;
    padding: 1 2;
    margin-bottom: 1;
}

/* ═══ Mockup parity: SWARM (multi-agent stream) ═══════════════════════ */

/* Attachment drop-card: file icon, resolved filename, Browse button. */
.swarm-file-card {
    layout: horizontal;
    width: 100%;
    height: 3;
    background: $bg_raised;
    border: solid $border;
    margin-bottom: 1;
    align: left middle;
}

.swarm-file-icon {
    color: $fg_accent;
    text-style: bold;
    width: 3;
}

.swarm-file-name {
    width: 1fr;
    color: $fg_primary;
    text-style: bold;
}

.swarm-file-input {
    width: 1fr;
    height: 1;
    background: $bg_raised;
    border: solid $border;
    color: $fg_primary;
}

/* Output Inspection header: caption on the left, view switch on the right. */
.output-inspection {
    layout: horizontal;
    width: 100%;
    /* Three rows: the segmented switch is a 3-row control, and a 1-row header
       clipped it to a bare fill with no visible label. */
    height: 3;
    margin-bottom: 0;
    align: left middle;
}

.output-inspection .card-caption {
    width: 1fr;
}

/* Stop / Restart action deck pinned under the swarm log. */
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

.btn-restart {
    width: 2fr;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

/* Terminal-style listener line under the swarm log. */
.listener-line {
    width: 100%;
    height: 1;
    color: $status_muted;
    text-style: italic;
}
"""
)

__all__ = ["THEME", "TUI_CSS"]
