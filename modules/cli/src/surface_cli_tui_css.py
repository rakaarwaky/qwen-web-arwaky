"""Obsidian Nebula design tokens and Textual CSS for the Qwen TUI application.

Surface layer (surface_cli): design-system colors and stylesheet string
consumed by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

# V1: single source of truth for Rich-markup colors (CSS tokens live in TUI_CSS).
THEME: dict[str, str] = {
    "accent": "#c0c1ff",
    "primary": "#d5e4fa",
    "muted": "#908fa0",
    "ok": "#10B981",
    "warn": "#F59E0B",
    "err": "#EF4444",
    "info": "#3B82F6",
    "bright": "#4ADE80",
}

TUI_CSS = """
/* ═══ Obsidian Nebula Design Tokens (V1) ══════════════════════════════ */
$bg-base:      #051424;
$bg-surface:   #010f1f;
$bg-raised:    #122031;
$bg-overlay:   #0e1c2d;
$bg-hover:     #1d2b3c;
$bg-active:    #283647;

$fg-primary:   #d5e4fa;
$fg-accent:    #c0c1ff;
$fg-muted:     #908fa0;
$fg-on-accent: #1000a9;

$border:       #464554;
$accent:       #8083ff;

$status-ok:    #10B981;
$status-warn:  #F59E0B;
$status-err:   #EF4444;
$status-info:  #3B82F6;
$status-muted: #64748B;

/* ─── Base ──────────────────────────────────────────────────────────── */
Screen {
    background: $bg-base;
    color: $fg-primary;
    layers: base modal;
}

Header {
    background: $bg-base;
    color: $fg-accent;
    border-bottom: solid $border;
    height: 3;
    dock: top;
}

Footer {
    background: $fg-accent;
    color: $fg-on-accent;
    height: 1;
    dock: bottom;
}

TabbedContent {
    height: 1fr;
    background: $bg-base;
}

Tabs {
    background: $bg-surface;
    border-bottom: solid $border;
    height: 3;
}

Tab {
    padding: 0 2;
    color: $fg-muted;
}

Tab.-active {
    color: $fg-primary;
    text-style: bold;
    background: $bg-active;
    border-bottom: solid $accent;
}

/* ─── Overview Tab ──────────────────────────────────────────────────────────── */
.overview-container {
    height: 1fr;
    width: 100%;
    padding: 1 2;
    background: $bg-base;
    overflow-y: auto;   /* L3: was hidden — now scrolls on short terminals */
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
    background: $bg-surface;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.metric-item {
    margin-right: 3;
    color: $fg-primary;
    text-style: bold;
}

#slots-table {
    height: auto;
    max-height: 16;
    background: $bg-surface;
    border: solid $border;
    margin-bottom: 1;
}

.template-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
}

/* ─── Slot Pane Container ──────────────────────────────────────────────────────────── */
.slot-container {
    height: 1fr;
    width: 100%;
    layout: horizontal;
    background: $bg-base;
}

.left-pane {
    width: 48%;
    min-width: 30;      /* L1: 40+40 overflowed < 85 cols; now 30+30 fits */
    height: 100%;
    background: $bg-surface;
    border-right: solid $border;
    padding: 1 2;
}

.right-pane {
    width: 52%;
    min-width: 30;
    height: 100%;
    background: $bg-overlay;
    padding: 1 2;
}

/* L1: reduced min-width allows reflow on narrow terminals (< 85 cols). */

.pane-title {
    background: $bg-base;
    color: $fg-accent;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
    border-bottom: solid $border;
    height: 3;
}

.field-label {
    color: $fg-primary;
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
    background: $bg-raised;
    border: solid $border;
    color: $fg-primary;
}

.field-input:focus {
    border: solid $fg-accent;
}

.btn-browse {
    width: 10;
    min-width: 10;
    margin-left: 1;
    background: $bg-hover;
    color: $fg-accent;
    border: solid $border;
}

.btn-browse:hover {
    background: $bg-active;
    border: solid $fg-accent;
}

.toggle-row {
    layout: horizontal;
    height: 3;
    background: $bg-raised;
    border: solid $border;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.toggle-label-box {
    width: 1fr;
}

.toggle-subtext {
    color: $fg-muted;
}

Switch {
    background: $bg-active;
}

Switch.-on {
    background: $accent;
}

.btn-slot-run {
    width: 100%;
    height: 3;
    background: $fg-accent;
    color: $fg-on-accent;
    border: solid $fg-accent;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-run:hover {
    background: $bg-base;
    color: $fg-accent;
}

.btn-slot-cancel {
    width: 100%;
    height: 3;
    background: #991B1B;          /* A1: white on #991B1B ≈ 8.3:1 (AA+AAA) */
    color: #ffffff;
    border: solid $status-err;    /* keep the bright red as outline, not fill */
    text-style: bold;
    margin-top: 1;
}

.btn-slot-cancel:hover {
    background: $bg-base;
    color: $status-err;
}

.slot-log-view {
    height: 1fr;
    max-width: 100%;
    background: $bg-base;
    border: solid $border;
    color: $fg-primary;
    padding: 1;
    overflow-x: hidden;
    overflow-y: auto;
}

/* U3: indeterminate loading indicator, hidden until a slot runs */
.slot-loading {
    display: none;
    height: 1;
    margin-bottom: 1;
}

.status-badge {
    color: $status-ok;
    text-style: bold;
}

#session-badge {
    color: $status-ok;
    text-style: bold;
    background: $bg-raised;
    padding: 0 1;
}

#session-badge.invalid {
    color: $status-warn;
}

/* ─── Modal File Picker ──────────────────────────────────────────────────────────── */
FilePickerModal {
    align: center middle;
    background: rgba(5, 20, 36, 0.85);
}

#modal-container {
    width: 80%;
    height: 80%;
    background: $bg-surface;
    border: double $fg-accent;
    padding: 1 2;
}

#modal-title {
    background: $bg-base;
    color: $fg-accent;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid $border;
    height: 3;
    width: 100%;
}

#modal-tree {
    width: 100%;
    height: 1fr;
    background: $bg-base;
    border: solid $border;
    margin: 1 0;
    color: $fg-primary;
}

#modal-btn-row {
    height: 3;
    width: 100%;
    align: right middle;
    margin-top: 1;
}

#btn-cancel-modal {
    width: 16;
    background: $bg-hover;
    color: $fg-accent;
    border: solid $border;
}

#btn-cancel-modal:hover {
    background: #991B1B;          /* A1: was $status-err @ ≈ 3.8:1 */
    color: #ffffff;
}

/* ─── Prompt Template Select ──────────────────────────────────────────────────────────── */
Select {
    width: 1fr;
    background: $bg-raised;
    border: solid $border;
    color: $fg-primary;
    margin-bottom: 1;
}

Select:focus {
    border: solid $fg-accent;
}

SelectOverlay {
    background: $bg-surface;
    border: solid $border;
    color: $fg-primary;
}

SelectOverlay > OptionList > .option-list--option-highlighted {
    background: $bg-active;
    color: $fg-accent;
}

/* ─── Help Screen (A4) ──────────────────────────────────────────────────────────── */
HelpScreen {
    align: center middle;
    background: rgba(5, 20, 36, 0.9);
}

#help-container {
    width: 72;
    max-width: 90%;
    height: auto;
    max-height: 90%;
    background: $bg-surface;
    border: double $fg-accent;
    padding: 1 2;
}

#help-title {
    background: $bg-base;
    color: $fg-accent;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid $border;
    height: 3;
    width: 100%;
    margin-bottom: 1;
}

#help-body {
    color: $fg-primary;
}

#help-close {
    width: 16;
    margin-top: 1;
    background: $bg-hover;
    color: $fg-accent;
    border: solid $border;
}
"""

__all__ = ["THEME", "TUI_CSS"]
