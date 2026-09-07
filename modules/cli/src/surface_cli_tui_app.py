"""Modern-Brutalist TUI interactive controller with Tab-per-Job-Slot architecture.

Surface layer (surface_cli): Textual application for parallel prompt execution,
attachment selection, per-slot live logging, and session setup matching Obsidian Nebula design system.
"""

from __future__ import annotations

import contextlib
import logging
import threading
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
    RichLog,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

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

TUI_CSS = """
/* ─── Obsidian Nebula Theme Colors ────────────────────────── */
Screen {
    background: #051424;
    color: #d5e4fa;
    layers: base modal;
}

Header {
    background: #051424;
    color: #c0c1ff;
    border-bottom: solid #464554;
    height: 3;
    dock: top;
}

Footer {
    background: #c0c1ff;
    color: #1000a9;
    height: 1;
    dock: bottom;
}

TabbedContent {
    height: 1fr;
    background: #051424;
}

Tabs {
    background: #010f1f;
    border-bottom: solid #464554;
    height: 3;
}

Tab {
    padding: 0 2;
    color: #908fa0;
}

Tab.-active {
    color: #c0c1ff;
    text-style: bold;
    background: #122031;
    border-bottom: solid #8083ff;
}

/* ─── Overview Tab ────────────────────────────────────────── */
.overview-container {
    height: 1fr;
    width: 100%;
    padding: 1 2;
    background: #051424;
}

.metrics-bar {
    layout: horizontal;
    height: 3;
    background: #010f1f;
    border: solid #464554;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.metric-item {
    margin-right: 3;
    color: #d5e4fa;
    text-style: bold;
}

#slots-table {
    height: 8;
    background: #010f1f;
    border: solid #464554;
    margin-bottom: 1;
}

.template-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
}

/* ─── Slot Pane Container ─────────────────────────────────── */
.slot-container {
    height: 1fr;
    width: 100%;
    layout: horizontal;
    background: #051424;
}

.left-pane {
    width: 48%;
    height: 100%;
    background: #010f1f;
    border-right: solid #464554;
    padding: 1 2;
}

.right-pane {
    width: 52%;
    height: 100%;
    background: #0e1c2d;
    padding: 1 2;
}

.pane-title {
    background: #051424;
    color: #c0c1ff;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
    border-bottom: solid #464554;
    height: 3;
}

.field-label {
    color: #d5e4fa;
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
    background: #122031;
    border: solid #464554;
    color: #d5e4fa;
}

.field-input:focus {
    border: solid #c0c1ff;
}

.btn-browse {
    width: 10;
    min-width: 10;
    margin-left: 1;
    background: #1d2b3c;
    color: #c0c1ff;
    border: solid #464554;
}

.btn-browse:hover {
    background: #283647;
    border: solid #c0c1ff;
}

.toggle-row {
    layout: horizontal;
    height: 3;
    background: #122031;
    border: solid #464554;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.toggle-label-box {
    width: 1fr;
}

.toggle-subtext {
    color: #908fa0;
}

Switch {
    background: #283647;
}

Switch.-on {
    background: #8083ff;
}

.btn-slot-run {
    width: 100%;
    height: 3;
    background: #c0c1ff;
    color: #1000a9;
    border: solid #c0c1ff;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-run:hover {
    background: #051424;
    color: #c0c1ff;
}

.btn-slot-cancel {
    width: 100%;
    height: 3;
    background: #EF4444;
    color: #ffffff;
    border: solid #EF4444;
    text-style: bold;
    margin-top: 1;
}

.btn-slot-cancel:hover {
    background: #051424;
    color: #EF4444;
}

.slot-log-view {
    height: 1fr;
    background: #051424;
    border: solid #464554;
    color: #d5e4fa;
    padding: 1;
}

.status-badge {
    color: #10B981;
    text-style: bold;
}

#session-badge {
    color: #10B981;
    text-style: bold;
    background: #122031;
    padding: 0 1;
}

#session-badge.invalid {
    color: #F59E0B;
}

/* ─── Modal File Picker ───────────────────────────────────── */
FilePickerModal {
    align: center middle;
    background: rgba(5, 20, 36, 0.85);
}

#modal-container {
    width: 80%;
    height: 80%;
    background: #010f1f;
    border: double #c0c1ff;
    padding: 1 2;
}

#modal-title {
    background: #051424;
    color: #c0c1ff;
    text-style: bold;
    padding: 0 1;
    border-bottom: solid #464554;
    height: 3;
    width: 100%;
}

#modal-tree {
    width: 100%;
    height: 1fr;
    background: #051424;
    border: solid #464554;
    margin: 1 0;
    color: #d5e4fa;
}

#modal-btn-row {
    height: 3;
    width: 100%;
    align: right middle;
    margin-top: 1;
}

#btn-cancel-modal {
    width: 16;
    background: #1d2b3c;
    color: #c0c1ff;
    border: solid #464554;
}

#btn-cancel-modal:hover {
    background: #EF4444;
    color: #ffffff;
}
/* ─── Prompt Template Select ──────────────────────────────── */
Select {
    width: 1fr;
    background: #122031;
    border: solid #464554;
    color: #d5e4fa;
    margin-bottom: 1;
}

Select:focus {
    border: solid #c0c1ff;
}

SelectOverlay {
    background: #010f1f;
    border: solid #464554;
    color: #d5e4fa;
}

SelectOverlay > OptionList > .option-list--option-highlighted {
    background: #283647;
    color: #c0c1ff;
}

.template-row {
    layout: horizontal;
    height: auto;
    margin-bottom: 1;
}
"""


class FilePickerModal(ModalScreen[str | None]):
    """Modal screen for visual file picking using DirectoryTree."""

    BINDINGS = [Binding("escape", "dismiss_modal", "Cancel")]

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("[ SELECT FILE — Navigate with arrows, press Enter on file to select ]", id="modal-title")
            yield DirectoryTree(str(self._start_path), id="modal-tree")
            with Horizontal(id="modal-btn-row"):
                yield Button("Cancel (Esc)", id="btn-cancel-modal")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-modal":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class QwenTuiLogHandler(logging.Handler):
    """Logging handler streaming stdlib and structlog records to Textual RichLog per slot."""

    def __init__(self, app: QwenTuiApp) -> None:
        super().__init__()
        self._app = app

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
                yield RichLog(id="log-view-overview", highlight=True, markup=True)

            # ─── Tabs 2..N: Job Slots ───────────────────────────
            for s in range(1, NUM_SLOTS + 1):
                with TabPane(f"Slot {s} 💤", id=f"tab-slot-{s}"), Horizontal(classes="slot-container"):
                    with ScrollableContainer(classes="left-pane"):
                        yield Static(f"[ CONFIGURATION: SLOT {s} ]", classes="pane-title")

                        yield Label("Prompt Template (Quick Select)", classes="field-label")
                        template_options = [
                            (meta["title"], role) for role, meta in PROMPT_TEMPLATE_MANIFEST.items()
                        ]
                        yield Select(
                            template_options,
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

                        yield Label("Attachment File (Optional)", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/attachment.file",
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
                        yield RichLog(id=f"log-view-{s}", highlight=True, markup=True, classes="slot-log-view")

        yield Footer()

    def on_mount(self) -> None:
        self._init_table()
        self._log_handler = QwenTuiLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(self._log_handler)

        self._log_msg("[bold #c0c1ff]Qwen Web Automation TUI initialized with multi-slot architecture.[/]")
        self._log_msg("[#908fa0]Each slot runs an independent Chromium process sharing login state.[/]")
        self._refresh_session_badge()

    def on_unmount(self) -> None:
        if hasattr(self, "_log_handler"):
            logging.getLogger().removeHandler(self._log_handler)

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
            self.query_one("#metric-active", Label).update(f"ACTIVE: {active}")
            self.query_one("#metric-done", Label).update(f"DONE: {done}")

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
                self._open_picker(f"input-file-{s}")
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
            self._log_msg(f"[bold #4ADE80]TEMPLATE:[/] Slot {slot_id} ← role '{role}'", slot_id)

    def _open_picker(self, target_input_id: str) -> None:
        self._target_field_for_picker = target_input_id

        def _on_picked(path: str | None) -> None:
            if path and self._target_field_for_picker:
                with contextlib.suppress(Exception):
                    field = self.query_one(f"#{self._target_field_for_picker}", Input)
                    field.value = path

        self.push_screen(FilePickerModal(), _on_picked)

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
            self._log_msg(f"[bold #F59E0B]WARNING:[/] Slot {slot_id} already running.", slot_id)
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
            self._log_msg(f"[bold #EF4444]ERROR:[/] {plan.message} (Slot {slot_id})", slot_id)
            return

        cfg = plan.config
        p_name = plan.prompt_path.name

        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {p_name[:12]} ⏳")
        self._update_slot_status(slot_id, "STATUS: RUNNING")
        self._slot_stats[slot_id] = {"status": "RUNNING", "file": p_name, "duration": 0.0}
        self._update_table_row(slot_id, "RUNNING ⏳", p_name, "running...")
        self._refresh_metrics()

        self._slot_workers[slot_id] = self._execute_slot_worker(slot_id, cfg)

    def _cancel_slot(self, slot_id: int) -> None:
        worker = self._slot_workers.get(slot_id)
        if worker is None:
            self._log_msg(f"[#908fa0]No run active in Slot {slot_id}.[/]", slot_id)
            return
        worker.cancel()
        self._slot_workers[slot_id] = None
        self._log_msg(f"[bold #F59E0B]CANCELLED:[/] Slot {slot_id} stopped by user.", slot_id)
        self._update_slot_status(slot_id, "STATUS: CANCELLED")
        self._set_slot_tab_title(slot_id, f"Slot {slot_id} 💤")
        self._slot_stats[slot_id]["status"] = "CANCELLED"
        self._update_table_row(slot_id, "CANCELLED ✕", self._slot_stats[slot_id]["file"], "stopped")
        self._refresh_metrics()

    @work(thread=True)
    def _execute_slot_worker(self, slot_id: int, cfg: AppConfig) -> None:
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        prompt_name = cfg.prompt_path.name if cfg.prompt_path else cfg.input_path.name
        self.call_from_thread(
            self._log_msg, f"[bold #c0c1ff]>>> [Slot {slot_id}] Starting browser for: {prompt_name}[/]", slot_id
        )

        import time

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
                self.call_from_thread(self._log_msg, f"[bold #EF4444][Slot {slot_id}] FAILED:[/] {res_str}", slot_id)
                self.call_from_thread(self._set_slot_tab_title, slot_id, f"Slot {slot_id}: {prompt_name[:12]} ❌")
                self.call_from_thread(self._update_slot_status, slot_id, "STATUS: FAILED")
                self._slot_stats[slot_id] = {"status": "FAILED", "file": prompt_name, "duration": dur}
                self.call_from_thread(self._update_table_row, slot_id, "FAILED ❌", prompt_name, f"{dur}s")
            else:
                self.call_from_thread(self._log_msg, f"[bold #10B981][Slot {slot_id}] SUCCESS:[/] {res_str}", slot_id)
                self.call_from_thread(self._set_slot_tab_title, slot_id, f"Slot {slot_id}: {prompt_name[:12]} ✅")
                self.call_from_thread(self._update_slot_status, slot_id, "STATUS: SUCCESS")
                self._slot_stats[slot_id] = {"status": "SUCCESS", "file": prompt_name, "duration": dur}
                self.call_from_thread(self._update_table_row, slot_id, "DONE ✅", prompt_name, f"{dur}s")
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(self._log_msg, f"[bold #EF4444][Slot {slot_id}] FAILED:[/] {exc}", slot_id)
            self.call_from_thread(self._set_slot_tab_title, slot_id, f"Slot {slot_id} ❌")
            self.call_from_thread(self._update_slot_status, slot_id, "STATUS: FAILED")
            self._slot_stats[slot_id] = {"status": "FAILED", "file": prompt_name, "duration": dur}
            self.call_from_thread(self._update_table_row, slot_id, "FAILED ❌", prompt_name, f"{dur}s")
        finally:
            self._slot_workers[slot_id] = None
            self.call_from_thread(self._refresh_metrics)

    def _set_slot_tab_title(self, slot_id: int, title: str) -> None:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            tab = tabs.get_tab(f"tab-slot-{slot_id}")
            tab.label = Content.from_text(title)

    def _update_slot_status(self, slot_id: int, status_text: str) -> None:
        with contextlib.suppress(Exception):
            badge = self.query_one(f"#status-badge-{slot_id}", Label)
            badge.update(status_text)

    def _ensure_log_handler(self) -> None:
        root = logging.getLogger()
        if hasattr(self, "_log_handler") and not any(isinstance(h, QwenTuiLogHandler) for h in root.handlers):
            root.addHandler(self._log_handler)

    def action_login_action(self) -> None:
        self._log_msg("[bold #c0c1ff]>>> Launching interactive session setup...[/]")
        self._login_worker()

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.setup_session()
            self.call_from_thread(self._log_msg, f"[bold #10B981]LOGIN RESULT:[/] {res}")
            self.call_from_thread(self._refresh_session_badge)
        except Exception as exc:
            self.call_from_thread(self._log_msg, f"[bold #EF4444]LOGIN FAILED:[/] {exc}")

    def action_init_action(self) -> None:
        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            self._log_msg(f"[bold #10B981]INIT:[/] Workspace initialized in {Path.cwd()}")
        except Exception as exc:
            self._log_msg(f"[bold #EF4444]INIT ERROR:[/] {exc}")

    def _refresh_session_badge(self) -> None:
        try:
            badge = self.query_one("#session-badge", Label)
        except (LookupError, AttributeError):
            return
        if self._session is None:
            badge.update("SESSION: N/A")
            return
        badge.update("SESSION: CHECKING...")
        self._session_check_worker()

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
        active = sum(1 for w in self._slot_workers.values() if w is not None)
        if active == 0:
            self.exit()
            return
        self._log_msg(
            f"[bold #F59E0B]WARNING:[/] {active} automation jobs in progress. Press Ctrl+Q again or cancel jobs."
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
