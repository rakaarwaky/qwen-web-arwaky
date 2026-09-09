"""Obsidian Nebula design tokens and Textual CSS for the Qwen TUI application.

Surface layer (surface_cli): design-system colors and stylesheet string
consumed by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

# V1/V4: single source of truth — derive THEME and CSS tokens from _COLORS.
_COLORS: dict[str, str] = {
    "fg_accent": "#c0c1ff",
    "fg_primary": "#d5e4fa",
    "fg_muted": "#908fa0",
    "fg_on_accent": "#1000a9",
    "accent": "#8083ff",
    "bg_base": "#051424",
    "bg_surface": "#010f1f",
    "bg_raised": "#122031",
    "bg_overlay": "#0e1c2d",
    "bg_hover": "#1d2b3c",
    "bg_active": "#283647",
    "border": "#464554",
    # V3: lighten status colors for text-on-dark (WCAG AA >= 4.5:1)
    "status_ok": "#34D399",
    "status_warn": "#FBBF24",
    "status_err": "#EF4444",
    "status_info": "#60A5FA",
    "status_muted": "#8B9BB4",  # A1: was #64748B ~3.8:1, now ~5.9:1
    "bright": "#4ADE80",
    # V2: danger tokens replacing hardcoded #991B1B
    "danger_bg": "#991B1B",
    "danger_fg": "#ffffff",
}

THEME: dict[str, str] = {
    "accent": _COLORS["fg_accent"],
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
_CSS_HEADER = "/* ═══ Obsidian Nebula Design Tokens (V1 — auto-generated) ═══ */\n" + _css_vars()

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
    color: $bg_base;
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
    border-bottom: solid $accent;
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
    min-height: 5;
    max-width: 100%;
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
    height: auto;
    max-height: 16;
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
    background: rgba(5, 20, 36, 0.85);
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
    background: rgba(5, 20, 36, 0.9);
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
"""
)

__all__ = ["THEME", "TUI_CSS"]
