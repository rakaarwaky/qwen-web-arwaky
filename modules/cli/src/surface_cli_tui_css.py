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

Header {
    background: $bg_base;
    color: $fg_accent;
    border-bottom: solid $border;
    height: 3;
    dock: top;
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
    overflow-y: auto;
}

#log-view-overview {
    height: 1fr;
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

#slots-table {
    height: 1fr;
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
    background: $bg_base;
    color: $fg_accent;
    border: solid $border;
}

.btn-copy-log:hover {
    background: $bg_raised;
    color: $fg_accent;
}

.btn-sessions-refresh,
.btn-sessions-login,
.btn-sessions-health {
    min-width: 12;
    padding: 0 1;
    background: $bg_raised;
    color: $fg_primary;
    border: solid $border;
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
    border: solid $accent;
}

.btn-sessions-login:hover {
    background: $bg_base;
    color: $accent;
}

/* --- Screen redesign: card accents and segmented controls -------------------
   The four redesign screens (Overview, Login, Chat, Swarm) express their
   primary actions as full-width filled bars and their mode switches as a
   paired segmented control. Both patterns reuse the existing surface stack
   so no new palette entries are required. */

/* Full-width primary action ("ADD ACCOUNT", "START"), matching the
   mobile card language, in which one dominant action fills the row. */
.btn-primary-full {
    width: 100%;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
    margin-bottom: 1;
}

.btn-primary-full:hover {
    background: $fg_accent;
    border: solid $fg_accent;
}

/* Segmented switch (Event Log / System Log, Summary / Full). The active
   segment is filled with the accent; the inactive one stays on a raised
   surface so the current mode is readable at a glance. */
.segswitch-btn {
    width: auto;
    min-width: 14;
    height: 3;
    margin-right: 1;
    background: $bg_raised;
    color: $fg_muted;
    border: solid $border;
}

.segswitch-btn:hover {
    background: $bg_hover;
    color: $fg_primary;
}

.segswitch-btn.segswitch-active {
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}

/* Cluster health bar: one cell per slot, recoloured per slot status to
   mirror the segmented meter in the Swarm Status card. */
.segment-bar {
    layout: horizontal;
    height: 1;
    width: 100%;
    background: $bg_base;
    margin-bottom: 1;
}

.segment-fill {
    width: 1fr;
    height: 1;
    color: $bg_active;
    text-style: bold;
}

.segment-idle {
    color: $bg_active;
}

.segment-running {
    color: $status_ok;
}

.segment-done {
    color: $accent;
}

.segment-failed {
    color: $status_err;
}

.segment-cancelled {
    color: $status_warn;
}

/* Raw system-log pane: a terminal-styled surface, visually distinct vs the event
   log, so the two Swarm views never read as the same widget. */
#log-view-swarm-system {
    height: 1fr;
    min-height: 3;
    background: $bg_surface;
    border: solid $border;
    color: $status_muted;
    padding: 1;
    overflow-x: hidden;
    overflow-y: auto;
}

#unified-stream-container {
    height: 1fr;
    min-height: 3;
}

#full-log-container {
    height: 1fr;
    min-height: 3;
}

.hidden {
    display: none;
}

/* Swarm action deck: stop sits left at natural width, start takes the
   remaining row so the destructive action never dominates the row. */
.swarm-actions {
    height: 3;
    margin-top: 1;
}

.btn-stop {
    width: 16;
    min-width: 16;
    height: 3;
    background: $danger_bg;
    color: $danger_fg;
    border: solid $status_err;
    text-style: bold;
}

.btn-stop:hover {
    background: $bg_base;
    color: $status_err;
}

.btn-start {
    width: 1fr;
    height: 3;
    background: $accent;
    color: $fg_on_accent;
    border: solid $accent;
    text-style: bold;
}
"""
)

__all__ = ["THEME", "TUI_CSS"]
