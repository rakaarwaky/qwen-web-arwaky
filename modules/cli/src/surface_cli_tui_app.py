"""Modern-Brutalist TUI interactive controller with Tab-per-Job-Slot architecture.

Surface layer (surface_cli): Textual application for parallel prompt execution,
attachment selection, per-slot live logging, and session setup matching Obsidian Nebula design system.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from pathlib import Path
from typing import Any, cast

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from modules.cli.src.surface_cli_session_setup import ConfirmModal
from modules.core.src.capabilities_tui_slot_config import SlotInputError, TuiSlotConfigResolver
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS, DEFAULT_OUTPUT, PROMPT_TEMPLATE_MANIFEST
from modules.shared.src.taxonomy_core_vo import AppConfig, FilePath, HeadlessFlag
from modules.shared.src.utility_core_response import detect_processing_failure
from modules.shared.src.utility_core_version import get_package_version

NUM_SLOTS = max(2, int(DEFAULT_MAX_WORKERS))

# Textual alt-chords only support a single digit (alt+0..9). Slots beyond 9
# fall back to ctrl+alt chords. alt+0 is reserved for the Overview tab.
_EXTRA_SLOT_KEYS: dict[int, str] = {s: f"ctrl+alt+{s - 10}" for s in range(10, 20)}

# V1: single source of truth for Rich-markup colors (CSS tokens live in TUI_CSS).
_THEME: dict[str, str] = {
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
    color: $fg-accent;
    text-style: bold;
    background: $bg-raised;
    border-bottom: solid $accent;
}

/* ─── Overview Tab ──────────────────────────────────────────────────────────── */
.overview-container {
    height: 1fr;
    width: 100%;
    padding: 1 2;
    background: $bg-base;
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
    min-width: 40;
    height: 100%;
    background: $bg-surface;
    border-right: solid $border;
    padding: 1 2;
}

.right-pane {
    width: 52%;
    min-width: 40;
    height: 100%;
    background: $bg-overlay;
    padding: 1 2;
}

/* L1: min-width guards keep panes usable on narrow terminals
   (Textual 8 has no @media support; min-width is the reflow guard). */

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
    background: $status-err;
    color: #ffffff;
    border: solid $status-err;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-cancel:hover {
    background: $bg-base;
    color: $status-err;
}

.slot-log-view {
    height: 1fr;
    background: $bg-base;
    border: solid $border;
    color: $fg-primary;
    padding: 1;
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
    background: $status-err;
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

.template-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
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



class FilePickerModal(ModalScreen[str | None]):
    """Modal screen for visual file picking using DirectoryTree."""

    BINDINGS = [Binding("escape", "dismiss_modal", "Cancel")]

    def __init__(
        self,
        start_path: Path | None = None,
        select_directories: bool = False,
        return_focus_id: str | None = None,  # A2: restore focus after dismiss
    ) -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()
        self._select_directories = select_directories
        self._current_path: Path = self._start_path
        self._return_focus_id = return_focus_id

    def compose(self) -> ComposeResult:
        title = "SELECT FILE OR FOLDER" if self._select_directories else "SELECT FILE"
        hint = (
            "press Enter on a file, or click 'Select This Folder'"
            if self._select_directories
            else "press Enter on file to select"
        )
        with Vertical(id="modal-container"):
            yield Label(f"[ {title} — {hint} ]", id="modal-title")
            yield DirectoryTree(str(self._start_path), id="modal-tree")
            with Horizontal(id="modal-btn-row"):
                if self._select_directories:
                    yield Button("Select This Folder", variant="primary", id="btn-select-folder")
                yield Button("Cancel (Esc)", id="btn-cancel-modal")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        # Accept regular files in both modes; folders are picked via the button.
        self.dismiss(str(event.path))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._current_path = Path(event.path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-modal":
            self.dismiss(None)
        elif event.button.id == "btn-select-folder":
            self.dismiss(str(self._current_path))

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    # A2: return focus to the invoking widget after dismissal.
    def on_dismiss(self) -> None:
        if self._return_focus_id:
            with contextlib.suppress(Exception):
                target = self.app.query_one(f"#{self._return_focus_id}")
                target.focus()


class HelpScreen(ModalScreen[None]):
    """A4: keyboard-shortcut reference overlay."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("q", "dismiss_modal", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Label("[ KEYBOARD SHORTCUTS ]", id="help-title")
            yield Static(
                "alt+0            Overview tab\n"
                "alt+1 .. alt+9   Slots 1-9\n"
                "ctrl+alt+0..9    Slots 10-19 (A3)\n"
                "enter / ctrl+r   Run active slot\n"
                "ctrl+l           Login / session setup\n"
                "ctrl+i           Init workspace\n"
                "ctrl+q           Quit (confirm when jobs running)\n"
                "escape           Dismiss modal / quit when idle\n"
                "?                This help screen\n\n"
                "Note: Textual alt-chords accept a single digit, so slots\n"
                "beyond 19 are reachable by mouse or the Overview table only.",
                id="help-body",
            )
            yield Button("Close", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class QwenTuiLogHandler(logging.Handler):
    """Logging handler streaming stdlib and structlog records to Textual RichLog per slot."""

    # P2: only surface records from the qwen-web stack. Third-party libraries
    # (urllib3, PIL, playwright, httpx, asyncio, ...) also emit through the
    # root logger and must not flood the TUI log views. Records on the root
    # logger itself (empty name) are kept.
    _APP_PREFIXES: tuple[str, ...] = (
        "qwen",
        "browser",
        "modules",
        "capabilities",
        "agent",
        "lifecycle",
        "utility",
        "shared",
        "core",
        "cli",
        "surface",
    )

    def __init__(self, app: QwenTuiApp) -> None:
        super().__init__()
        self._app = app

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name or ""
        return not name or name.startswith(self._APP_PREFIXES)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            name = record.name
            lvl = record.levelname

            msg_esc = escape(msg)
            name_esc = escape(name)
            lvl_esc = escape(lvl)

            if record.levelno >= logging.ERROR:
                line = f"[bold #EF4444][{lvl_esc}][{name_esc}][/] [#EF4444]{msg_esc}[/]"
            elif record.levelno >= logging.WARNING:
                line = f"[bold #F59E0B][{lvl_esc}][{name_esc}][/] [#F59E0B]{msg_esc}[/]"
            elif record.levelno >= logging.INFO:
                line = f"[bold #3B82F6][{name_esc}][/] [#d5e4fa]{msg_esc}[/]"
            else:
                line = f"[#64748B][{name_esc}][/] [#908fa0]{msg_esc}[/]"

            slot_id: int | None = None
            if record.threadName and record.threadName.startswith("qwen_slot_worker_"):
                with contextlib.suppress(Exception):
                    slot_id = int(record.threadName.split("_")[-1])

            with contextlib.suppress(RuntimeError):
                self._app.call_from_thread(self._app._log_msg, line, slot_id)
        except Exception:
            self.handleError(record)


_APP_VERSION = get_package_version()


class QwenTuiApp(App[None]):
    """Obsidian Nebula Terminal User Interface for Qwen Web Automation with Tab-per-Job-Slot."""

    CSS = TUI_CSS
    TITLE = f"QWEN-CLI {_APP_VERSION} "
    SUB_TITLE = "chat.qwen.ai parallel automation engine"

    # alt+0 → Overview, alt+1..9 → Slot 1..9, ctrl+alt+0 → Slot 10.
    BINDINGS = [
        Binding("alt+0", "switch_tab_overview", "Overview"),
        *[
            Binding(
                f"alt+{s}" if s <= 9 else _EXTRA_SLOT_KEYS[s],
                f"switch_tab_slot({s})",
                f"Slot {s}",
            )
            for s in range(1, NUM_SLOTS + 1)
        ],
        Binding("enter", "run_active_slot", "Run Slot"),
        Binding("ctrl+r", "run_active_slot", "Run"),
        Binding("ctrl+l", "login_action", "Login"),
        Binding("ctrl+i", "init_action", "Init"),
        Binding("ctrl+q", "request_quit", "Quit"),
        Binding("escape", "request_quit", "Exit"),
        Binding("question_mark", "show_help", "Help"),  # A4
    ]

    def __init__(
        self,
        workspace: IWorkspaceProtocol,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        setup: ISetupAggregate | None = None,
        session: ISessionAggregate | None = None,
        jobs: IJobManagerAggregate | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._setup = setup
        self._session = session
        self._jobs = jobs
        self._slot_config = TuiSlotConfigResolver()
        self._target_field_for_picker: str | None = None
        self._slot_workers: dict[int, Any] = {}
        self._slot_stats: dict[int, dict[str, Any]] = {
            s: {"status": "IDLE", "file": "-", "duration": 0.0} for s in range(1, NUM_SLOTS + 1)
        }
        # C5: build template options / roles once instead of per-compose.
        self._template_options: list[tuple[str, str]] = [
            (meta["title"], role) for role, meta in PROMPT_TEMPLATE_MANIFEST.items()
        ]
        self._template_roles: set[str] = set(PROMPT_TEMPLATE_MANIFEST)
        # P3: widget refs cached at mount time.
        self._metric_active: Label | None = None
        self._metric_done: Label | None = None
        # U4: session-check timeout flag.
        self._session_check_timed_out = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            # ─── Tab 1: Overview ────────────────────────────────
            with TabPane("Overview 📊", id="tab-overview"), Vertical(classes="overview-container"):
                with Horizontal(classes="metrics-bar"):
                    yield Label(f"SLOTS: {NUM_SLOTS}", id="metric-slots", classes="metric-item")
                    yield Label("ACTIVE: 0", id="metric-active", classes="metric-item")
                    yield Label("DONE: 0", id="metric-done", classes="metric-item")
                    yield Label("SESSION: CHECKING...", id="session-badge", classes="metric-item")

                yield Label("Active Job Slots (1 Browser per Job)", classes="field-label")
                yield DataTable(id="slots-table")

                yield Label("System Event Log", classes="field-label")
                yield RichLog(id="log-view-overview", highlight=True, markup=True, max_lines=2000)  # P1

            # ─── Tabs 2..N: Job Slots ───────────────────────────
            for s in range(1, NUM_SLOTS + 1):
                with TabPane(f"Slot {s} 💤", id=f"tab-slot-{s}"), Horizontal(classes="slot-container"):
                    with ScrollableContainer(classes="left-pane"):
                        yield Static(f"[ CONFIGURATION: SLOT {s} ]", classes="pane-title")

                        yield Label("Prompt Template (Quick Select)", classes="field-label")
                        yield Select(
                            self._template_options,
                            prompt="Select a template or type file path below",
                            allow_blank=True,
                            id=f"select-template-{s}",
                        )

                        yield Label("Prompt File / Role (Required) *", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/prompt.md or role (architect|backend|frontend|analyst)",
                                id=f"input-prompt-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-prompt-{s}", classes="btn-browse")

                        yield Label("Attachment File or Folder (Optional)", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/file or folder",
                                id=f"input-file-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-file-{s}", classes="btn-browse")

                        yield Label("Output Destination", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value=str(DEFAULT_OUTPUT),
                                placeholder="path/to/output.md",
                                id=f"input-output-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-output-{s}", classes="btn-browse")

                        with Horizontal(classes="toggle-row"):
                            with Vertical(classes="toggle-label-box"):
                                yield Label("Headless Browser", classes="field-label")
                                yield Label("1 independent browser in background", classes="toggle-subtext")
                            yield Switch(value=True, id=f"switch-headless-{s}")

                        yield Button(
                            f"⚡ RUN IN SLOT {s}", variant="primary", id=f"btn-run-{s}", classes="btn-slot-run"
                        )
                        yield Button(f"✕ Cancel Slot {s}", id=f"btn-cancel-{s}", classes="btn-slot-cancel")

                    with Vertical(classes="right-pane"):
                        with Horizontal(classes="pane-title"):
                            yield Label(f"[ LIVE LOG: BROWSER #{s} ]", classes="field-label")
                            yield Label("STATUS: READY", id=f"status-badge-{s}", classes="status-badge")
                        yield LoadingIndicator(id=f"loading-{s}", classes="slot-loading")  # U3
                        yield RichLog(  # P1: bounded log buffer
                            id=f"log-view-{s}",
                            highlight=True,
                            markup=True,
                            classes="slot-log-view",
                            max_lines=2000,
                        )

        yield Footer()

    def on_mount(self) -> None:
        self._init_table()
        self._log_handler = QwenTuiLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(self._log_handler)

        # P3: cache metric widget refs once; no per-call DOM lookups.
        self._metric_active = self.query_one("#metric-active", Label)
        self._metric_done = self.query_one("#metric-done", Label)

        self._log_msg(f"[bold {_THEME['accent']}]Qwen Web Automation TUI initialized with multi-slot architecture.[/]")
        self._log_msg(f"[{_THEME['muted']}]Each slot runs an independent Chromium process sharing login state.[/]")

        # U5: seed per-slot log views with an empty-state hint.
        for s in range(1, NUM_SLOTS + 1):
            with contextlib.suppress(Exception):
                log_view = self.query_one(f"#log-view-{s}", RichLog)
                log_view.write(f"[{_THEME['muted']}]Set a prompt file, then press Enter or RUN.[/]")

        self._refresh_session_badge()

    def on_unmount(self) -> None:
        if hasattr(self, "_log_handler"):
            logging.getLogger().removeHandler(self._log_handler)
        # U2: best-effort cancellation of any still-running slot workers so
        # their Chromium child processes are not left orphaned on exit.
        for worker in list(self._slot_workers.values()):
            if worker is not None:
                with contextlib.suppress(Exception):
                    worker.cancel()

    def _init_table(self) -> None:
        with contextlib.suppress(Exception):
            table = self.query_one("#slots-table", DataTable)
            table.add_columns("Slot", "Status", "Prompt File", "Duration")
            for s in range(1, NUM_SLOTS + 1):
                table.add_row(f"Slot {s}", "IDLE 💤", "-", "0.0s", key=f"row-slot-{s}")

    def _update_table_row(self, slot_id: int, status: str, filename: str, duration: str) -> None:
        with contextlib.suppress(Exception):
            table = self.query_one("#slots-table", DataTable)
            table.update_cell(f"row-slot-{slot_id}", "Status", status)
            table.update_cell(f"row-slot-{slot_id}", "Prompt File", filename)
            table.update_cell(f"row-slot-{slot_id}", "Duration", duration)

    def _refresh_metrics(self) -> None:
        with contextlib.suppress(Exception):
            active = sum(1 for s in self._slot_stats.values() if s.get("status") == "RUNNING")
            done = sum(1 for s in self._slot_stats.values() if s.get("status") in {"SUCCESS", "FAILED"})
            # P3: cached widget refs (set in on_mount) — no DOM lookups here.
            if self._metric_active is not None:
                self._metric_active.update(f"ACTIVE: {active}")
            if self._metric_done is not None:
                self._metric_done.update(f"DONE: {done}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        for s in range(1, NUM_SLOTS + 1):
            if button_id == f"btn-run-{s}":
                self._run_slot(s)
                return
            if button_id == f"btn-cancel-{s}":
                self._cancel_slot(s)
                return
            if button_id == f"btn-browse-prompt-{s}":
                self._open_picker(f"input-prompt-{s}")
                return
            if button_id == f"btn-browse-file-{s}":
                self._open_picker(f"input-file-{s}", select_directories=True)
                return
            if button_id == f"btn-browse-output-{s}":
                self._open_picker(f"input-output-{s}")
                return

    def on_select_changed(self, event: Select.Changed) -> None:
        select_id = event.select.id or ""
        if not select_id.startswith("select-template-"):
            return
        slot_id = int(select_id.split("-")[-1])
        role = event.value
        if role is None:
            return
        with contextlib.suppress(Exception):
            prompt_input = self.query_one(f"#input-prompt-{slot_id}", Input)
            prompt_input.value = str(role)
            self._log_msg(f"[bold {_THEME['bright']}]TEMPLATE:[/] Slot {slot_id} ← role '{escape(str(role))}'", slot_id)
            # U8: optimistic existence hint when the picked value is a file path.
            if str(role) not in self._template_roles and not Path(str(role)).exists():
                self._log_msg(
                    f"[{_THEME['warn']}]WARNING:[/] '{escape(str(role))}' is not a known role and the file does not exist.",
                    slot_id,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """U6: keep the template Select in sync with manual path/role entry."""
        input_id = event.input.id or ""
        if not input_id.startswith("input-prompt-"):
            return
        slot_id = int(input_id.split("-")[-1])
        value = event.value.strip()
        with contextlib.suppress(Exception):
            select = self.query_one(f"#select-template-{slot_id}", Select)
            if value in self._template_roles:
                select.value = value
            elif select.value not in (None, Select.BLANK) and select.value != value:
                select.value = Select.BLANK

    def _open_picker(self, target_input_id: str, select_directories: bool = False) -> None:
        self._target_field_for_picker = target_input_id
        # A2: return focus to the Browse button that opened the picker.
        return_focus_id = f"btn-browse-{target_input_id.removeprefix('input-')}"

        def _on_picked(path: str | None) -> None:
            if path and self._target_field_for_picker:
                with contextlib.suppress(Exception):
                    field = self.query_one(f"#{self._target_field_for_picker}", Input)
                    field.value = path

        self.push_screen(
            FilePickerModal(
                select_directories=select_directories,
                return_focus_id=return_focus_id,
            ),
            _on_picked,
        )

    def _get_active_slot_id(self) -> int:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            active_id = tabs.active or ""
            if active_id.startswith("tab-slot-"):
                return int(active_id.split("-")[-1])
        return 1

    def action_run_active_slot(self) -> None:
        slot_id = self._get_active_slot_id()
        self._run_slot(slot_id)

    def action_switch_tab_overview(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-overview"

    def _switch_to_slot(self, slot_id: int) -> None:
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = f"tab-slot-{slot_id}"

    def action_switch_tab_slot(self, slot_id: int) -> None:
        self._switch_to_slot(int(slot_id))

    def _run_slot(self, slot_id: int) -> None:
        if self._slot_workers.get(slot_id) is not None:
            self._log_msg(f"[bold {_THEME['warn']}]WARNING:[/] Slot {slot_id} already running.", slot_id)
            return

        try:
            prompt_val = self.query_one(f"#input-prompt-{slot_id}", Input).value
            file_val = self.query_one(f"#input-file-{slot_id}", Input).value
            out_val = self.query_one(f"#input-output-{slot_id}", Input).value
            headless_val = self.query_one(f"#switch-headless-{slot_id}", Switch).value
        except Exception:
            return

        plan = self._slot_config.resolve_slot_run_plan(prompt_val, file_val, out_val, headless_val)
        if isinstance(plan, SlotInputError):
            # C1: escape the runtime message; A2: mirror to Overview + toast.
            msg = f"[bold {_THEME['err']}]ERROR:[/] {escape(str(plan.message))} (Slot {slot_id})"
            self._log_msg(msg, slot_id)
            self._log_msg(msg)
            with contextlib.suppress(Exception):
                self.notify(str(plan.message), severity="error", title=f"Slot {slot_id}")
            return

        cfg = plan.config
        p_name = plan.prompt_path.name

        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(p_name)} ⏳")
        self._update_slot_status(slot_id, "STATUS: RUNNING")
        self._slot_stats[slot_id] = {"status": "RUNNING", "file": p_name, "duration": 0.0}
        self._update_table_row(slot_id, "RUNNING ⏳", p_name, "running...")
        self._refresh_metrics()
        # U3: show indeterminate loading indicator while the job runs.
        with contextlib.suppress(Exception):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_slot_worker(slot_id, cfg)

    def _cancel_slot(self, slot_id: int) -> None:
        worker = self._slot_workers.get(slot_id)
        if worker is None:
            self._log_msg(f"[{_THEME['muted']}]No run active in Slot {slot_id}.[/]", slot_id)
            return
        worker.cancel()
        self._slot_workers[slot_id] = None
        self._log_msg(f"[bold {_THEME['warn']}]CANCELLED:[/] Slot {slot_id} stopped by user.", slot_id)
        self._update_slot_status(slot_id, "STATUS: CANCELLED")
        self._set_slot_tab_title(slot_id, f"Slot {slot_id} 💤")
        self._slot_stats[slot_id]["status"] = "CANCELLED"
        self._update_table_row(slot_id, "CANCELLED ✕", self._slot_stats[slot_id]["file"], "stopped")
        self._refresh_metrics()
        with contextlib.suppress(Exception):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    def _finalize_slot(self, slot_id: int, status: str, filename: str, duration: float, ok: bool) -> None:
        """C2: UI-thread-only finalizer — mutate slot state and update all surfaces atomically.

        Called via ``call_from_thread`` from the worker so ``_slot_stats`` /
        ``_slot_workers`` are never written from a background thread.
        """
        icon = "✅" if ok else "❌"
        self._slot_workers[slot_id] = None
        self._slot_stats[slot_id] = {"status": status, "file": filename, "duration": duration}
        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(filename)} {icon}")
        self._update_slot_status(slot_id, f"STATUS: {status}")
        self._update_table_row(slot_id, f"{'DONE' if ok else 'FAILED'} {icon}", filename, f"{duration}s")
        self._refresh_metrics()
        # U3: hide the indeterminate loading indicator once the slot finishes.
        with contextlib.suppress(Exception):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    @work(thread=True)
    def _execute_slot_worker(self, slot_id: int, cfg: AppConfig) -> None:
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        prompt_name = cfg.prompt_path.name if cfg.prompt_path else cfg.input_path.name
        self.call_from_thread(
            self._log_msg,
            f"[bold {_THEME['accent']}]>>> [Slot {slot_id}] Starting browser for: {escape(prompt_name)}[/]",
            slot_id,
        )

        start_t = time.perf_counter()

        try:
            if cfg.file_path:
                res = self._attachment.process_prompt_with_attachment(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    attachment_file=cfg.file_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                )
            else:
                res = self._file_only.process_prompt_file_only(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                )
            dur = round(time.perf_counter() - start_t, 1)
            res_str = str(res)
            is_dict_err = isinstance(cast(Any, res), dict) and cast(dict[str, Any], res).get("status") in {
                "error",
                "failure",
                "failed",
            }
            fail_reason = detect_processing_failure(res_str)

            if is_dict_err or fail_reason:
                self.call_from_thread(
                    self._log_msg,
                    f"[bold {_THEME['err']}][Slot {slot_id}] FAILED:[/] {escape(res_str)}",
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False)
            else:
                self.call_from_thread(
                    self._log_msg,
                    f"[bold {_THEME['ok']}][Slot {slot_id}] SUCCESS:[/] {escape(res_str)}",
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", prompt_name, dur, True)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                f"[bold {_THEME['err']}][Slot {slot_id}] FAILED:[/] {escape(str(exc))}",
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False)

    def _set_slot_tab_title(self, slot_id: int, title: str) -> None:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            tab = tabs.get_tab(f"tab-slot-{slot_id}")
            tab.label = Content.from_text(title)

    # A1: every status carries a text+glyph prefix so meaning never relies on
    # color alone (WCAG 1.4.1). Glyphs are ASCII-safe for older terminals.
    _STATUS_ICONS: dict[str, str] = {
        "STATUS: READY": "● READY",
        "STATUS: RUNNING": "▶ RUNNING",
        "STATUS: SUCCESS": "✓ SUCCESS",
        "STATUS: FAILED": "✕ FAILED",
        "STATUS: CANCELLED": "■ CANCELLED",
    }

    @staticmethod
    def _truncate_name(name: str, limit: int = 12) -> str:
        """L3: truncate with an ellipsis instead of a hard cut."""
        return name if len(name) <= limit else name[: limit - 1] + "…"

    def _update_slot_status(self, slot_id: int, status_text: str) -> None:
        with contextlib.suppress(Exception):
            badge = self.query_one(f"#status-badge-{slot_id}", Label)
            badge.update(self._STATUS_ICONS.get(status_text, status_text))

    def _ensure_log_handler(self) -> None:
        root = logging.getLogger()
        if hasattr(self, "_log_handler") and not any(isinstance(h, QwenTuiLogHandler) for h in root.handlers):
            root.addHandler(self._log_handler)

    def action_show_help(self) -> None:
        """A4: push the keyboard-shortcut reference overlay."""
        self.push_screen(HelpScreen())

    def action_login_action(self) -> None:
        # U3: re-entrancy guard — one login flow at a time.
        if getattr(self, "_login_in_flight", False):
            self._log_msg(f"[bold {_THEME['warn']}]WARNING:[/] Login already in progress.")
            return
        self._login_in_flight = True
        self._log_msg(f"[bold {_THEME['accent']}]>>> Launching interactive session setup...[/]")
        self._login_worker()

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.setup_session()
            self.call_from_thread(self._log_msg, f"[bold {_THEME['ok']}]LOGIN RESULT:[/] {escape(str(res))}")
            self.call_from_thread(self._refresh_session_badge)
        except Exception as exc:
            self.call_from_thread(self._log_msg, f"[bold {_THEME['err']}]LOGIN FAILED:[/] {escape(str(exc))}")
        finally:
            self._login_in_flight = False

    def action_init_action(self) -> None:
        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            cwd = Path.cwd()
            self._log_msg(f"[bold {_THEME['ok']}]INIT:[/] Workspace initialized in {escape(str(cwd))}")
        except Exception as exc:
            self._log_msg(f"[bold {_THEME['err']}]INIT ERROR:[/] {escape(str(exc))}")

    def _refresh_session_badge(self) -> None:
        try:
            badge = self.query_one("#session-badge", Label)
        except (LookupError, AttributeError):
            return
        if self._session is None:
            badge.update("SESSION: N/A")
            return
        badge.update("SESSION: CHECKING...")
        # U4: if validation hangs (stale browser lock etc.), fall back to a
        # TIMEOUT state instead of showing CHECKING... forever.
        self._session_check_timed_out = False
        self.set_timer(15.0, self._session_check_timeout)
        self._session_check_worker()

    def _session_check_timeout(self) -> None:
        if self._session_check_timed_out:
            return
        self._session_check_timed_out = True
        with contextlib.suppress(Exception):
            badge = self.query_one("#session-badge", Label)
            badge.update("SESSION: TIMEOUT — run 'qwen-web-cli doctor'")
            badge.set_classes("invalid")

    @work(thread=True)
    def _session_check_worker(self) -> None:
        if self._session is None:
            self.call_from_thread(self._apply_session_badge, False)
            return
        try:
            valid, _msg = self._session.validate_session()
        except Exception:
            valid = False
        self.call_from_thread(self._apply_session_badge, valid)

    def _apply_session_badge(self, valid: bool) -> None:
        try:
            badge = self.query_one("#session-badge", Label)
        except (LookupError, AttributeError):
            return
        badge.update("SESSION: VALID" if valid else "SESSION: EXPIRED")
        badge.set_classes("invalid" if not valid else "")

    def action_request_quit(self) -> None:
        active = [s for s, w in self._slot_workers.items() if w is not None]
        if not active:
            self.exit()
            return

        # U2: never quit silently while jobs are running — confirm first and
        # cancel the workers so Chromium processes are not left orphaned.
        def _confirmed(confirmed: bool | None) -> None:
            if confirmed:
                for s in active:
                    self._cancel_slot(s)
                self.exit()

        self.push_screen(
            ConfirmModal(
                "Confirm Quit",
                f"{len(active)} automation job(s) are still running.\n"
                "Quitting will cancel them. Browser processes will be stopped.",
            ),
            _confirmed,
        )

    def _log_msg(self, msg: str, slot_id: int | None = None) -> None:
        with contextlib.suppress(Exception):
            if slot_id is not None:
                log_view = self.query_one(f"#log-view-{slot_id}", RichLog)
                log_view.write(msg)
            else:
                with contextlib.suppress(Exception):
                    self.query_one("#log-view-overview", RichLog).write(msg)
                with contextlib.suppress(Exception):
                    active_slot = self._get_active_slot_id()
                    self.query_one(f"#log-view-{active_slot}", RichLog).write(msg)


__all__ = [
    "FilePickerModal",
    "QwenTuiApp",
    "QwenTuiLogHandler",
]
