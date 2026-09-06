"""Modern-Brutalist TUI interactive controller matching Obsidian Nebula design system.

Surface layer (surface_cli): Textual application for interactive prompt execution,
attachment selection, live logging, and session setup.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any, cast

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    Switch,
)

from modules.core.src.utility_core_config_factory import build_app_config
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_vo import AppConfig, FilePath, HeadlessFlag
from modules.shared.src.utility_core_prompt_template import is_prompt_role, materialize_role_template
from modules.shared.src.utility_core_response import detect_processing_failure
from modules.shared.src.utility_core_version import get_package_version

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

#main-container {
    height: 1fr;
    width: 100%;
    layout: horizontal;
    background: #051424;
}

/* ─── Left Pane: Execution Form ───────────────────────────── */
#left-pane {
    width: 50%;
    height: 100%;
    background: #010f1f;
    border-right: solid #464554;
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

.field-block {
    margin-bottom: 1;
    height: auto;
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

#btn-run {
    width: 100%;
    height: 3;
    background: #c0c1ff;
    color: #1000a9;
    border: solid #c0c1ff;
    text-style: bold;
    margin-top: 1;
}

#btn-run:hover {
    background: #051424;
    color: #c0c1ff;
}

/* ─── Right Pane: Live Log & Monitor ──────────────────────── */
#right-pane {
    width: 50%;
    height: 100%;
    background: #0e1c2d;
    padding: 1 2;
}

#log-view {
    height: 1fr;
    background: #051424;
    border: solid #464554;
    color: #d5e4fa;
    padding: 1;
}

#status-badge {
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

#btn-cancel {
    width: 100%;
    height: 3;
    background: #EF4444;
    color: #ffffff;
    border: solid #EF4444;
    text-style: bold;
    margin-top: 1;
}

#btn-cancel:hover {
    background: #051424;
    color: #EF4444;
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
    """Logging handler streaming stdlib and structlog records to Textual RichLog in real-time."""

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

            with contextlib.suppress(RuntimeError):
                self._app.call_from_thread(self._app._log_msg, line)
        except Exception:
            self.handleError(record)


def _default_prompt_value() -> str:
    return ""


def _default_file_value() -> str:
    return ""


_APP_VERSION = get_package_version()


class QwenTuiApp(App[None]):
    """Obsidian Nebula Terminal User Interface for Qwen Web Automation."""

    CSS = TUI_CSS
    TITLE = f"QWEN-CLI {_APP_VERSION} "
    SUB_TITLE = "chat.qwen.ai automation engine"

    BINDINGS = [
        Binding("enter", "run_action", "Run"),
        Binding("ctrl+l", "login_action", "Login"),
        Binding("ctrl+i", "init_action", "Init"),
        Binding("ctrl+r", "reset_action", "Reset"),
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
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._setup = setup
        self._session = session
        self._target_field_for_picker: str | None = None
        self._run_worker: Any | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            # ─── Left Pane: Config ──────────────────────────────
            with ScrollableContainer(id="left-pane"):
                yield Static("[ EXECUTION CONFIGURATION ]", classes="pane-title")

                default_prompt = _default_prompt_value()
                default_file = _default_file_value()

                # Prompt file
                yield Label("Prompt File (Required) *", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(
                        value=default_prompt,
                        placeholder="path/to/prompt.md or role (architect|backend|frontend|analyst)",
                        id="input-prompt",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-prompt", classes="btn-browse")

                # Attachment file
                yield Label("Attachment File (Optional)", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(
                        value=default_file,
                        placeholder="path/to/attachment.file",
                        id="input-file",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-file", classes="btn-browse")

                # Output path
                yield Label("Output Destination", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(
                        value=str(DEFAULT_OUTPUT),
                        placeholder="path/to/output.md",
                        id="input-output",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-output", classes="btn-browse")

                # Toggles
                with Horizontal(classes="toggle-row"):
                    with Vertical(classes="toggle-label-box"):
                        yield Label("Headless Browser", classes="field-label")
                        yield Label("Run automation in background without browser UI", classes="toggle-subtext")
                    yield Switch(value=True, id="switch-headless")

                yield Button("⚡ RUN AUTOMATION [Enter]", variant="primary", id="btn-run")
                yield Button("✕ Cancel Run", id="btn-cancel")

            # ─── Right Pane: Log Monitor ────────────────────────
            with Vertical(id="right-pane"):
                with Horizontal(classes="pane-title"):
                    yield Label("[ PREVIEW & LIVE LOG ]", classes="field-label")
                    yield Label("SESSION: CHECKING", id="session-badge")
                    yield Label("STATUS: READY", id="status-badge")
                yield RichLog(id="log-view", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        self._log_view = self.query_one("#log-view", RichLog)
        self._log_view.write("[bold #c0c1ff]Qwen Web Automation CLI initialized.[/]")
        self._log_view.write("[#908fa0]Ready for prompt dispatch. Fill fields on the left and hit Enter.[/]\n")

        self._log_handler = QwenTuiLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(self._log_handler)

        self._refresh_session_badge()

    def on_unmount(self) -> None:
        if hasattr(self, "_log_handler"):
            logging.getLogger().removeHandler(self._log_handler)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-run":
            self.action_run_action()
        elif button_id == "btn-cancel":
            self.action_cancel_run()
        elif button_id == "btn-browse-prompt":
            self._open_picker("input-prompt")
        elif button_id == "btn-browse-file":
            self._open_picker("input-file")
        elif button_id == "btn-browse-output":
            self._open_picker("input-output")

    def action_cancel_run(self) -> None:
        worker = getattr(self, "_run_worker", None)
        if worker is None:
            self._log_msg("[#908fa0]No automation run in progress.[/]")
            return
        worker.cancel()
        self._run_worker = None
        self._log_msg("[bold #F59E0B]CANCELLED:[/] Automation run stopped by user.")
        self._update_status("STATUS: READY")

    def _open_picker(self, target_input_id: str) -> None:
        self._target_field_for_picker = target_input_id

        def _on_picked(path: str | None) -> None:
            if path and self._target_field_for_picker:
                field = self.query_one(f"#{self._target_field_for_picker}", Input)
                field.value = path

        self.push_screen(FilePickerModal(), _on_picked)

    def action_run_action(self) -> None:
        if getattr(self, "_run_worker", None) is not None:
            self._log_msg("[bold #F59E0B]WARNING:[/] Automation already running. Cancel it first.")
            return

        prompt_val = self.query_one("#input-prompt", Input).value.strip()
        if not prompt_val:
            self._log_msg("[bold #EF4444]ERROR:[/] Prompt file is required.")
            return

        if is_prompt_role(prompt_val):
            p_path = materialize_role_template(prompt_val)
        else:
            p_path = Path(prompt_val).resolve()
            if not p_path.exists():
                self._log_msg(f"[bold #EF4444]ERROR:[/] Prompt file not found: {prompt_val}")
                return

        file_val = self.query_one("#input-file", Input).value.strip()
        f_path = Path(file_val).resolve() if file_val else None
        if f_path and not f_path.exists():
            self._log_msg(f"[bold #EF4444]ERROR:[/] Attachment file not found: {file_val}")
            return

        out_val = self.query_one("#input-output", Input).value.strip()
        out_path = Path(out_val).resolve() if out_val else DEFAULT_OUTPUT

        headless_val = self.query_one("#switch-headless", Switch).value

        cfg = build_app_config(
            mode="single",
            input_path=p_path,
            output_path=out_path,
            prompt_file=p_path,
            prompt_path=p_path,
            file_path=f_path,
            headless=headless_val,
            request_timeout=120,
        )

        self._run_worker = self._execute_worker(cfg)

    @work(thread=True)
    def _execute_worker(self, cfg: AppConfig) -> None:
        self._ensure_log_handler()
        self.call_from_thread(self._update_status, "STATUS: RUNNING")
        prompt_name = cfg.prompt_path.name if cfg.prompt_path else cfg.input_path.name
        self.call_from_thread(self._log_msg, f"[bold #c0c1ff]>>> Starting automation for: {prompt_name}[/]")
        if cfg.file_path:
            self.call_from_thread(self._log_msg, f"[#b9c8dd]    Attaching: {cfg.file_path.name}[/]")
        msg = f"[#908fa0]    Headless: {cfg.headless} | Timeout: {cfg.request_timeout}s[/]"
        self.call_from_thread(self._log_msg, msg)

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
            res_str = str(res)
            is_dict_err = isinstance(cast(Any, res), dict) and cast(dict[str, Any], res).get("status") in {
                "error",
                "failure",
                "failed",
            }
            fail_reason = detect_processing_failure(res_str)
            if is_dict_err or fail_reason:
                self.call_from_thread(self._log_msg, f"[bold #EF4444]FAILED:[/] {res_str}")
            else:
                self.call_from_thread(self._log_msg, f"[bold #10B981]SUCCESS:[/] {res_str}")
        except Exception as exc:
            self.call_from_thread(self._log_msg, f"[bold #EF4444]FAILED:[/] {exc}")
        finally:
            self._run_worker = None
            self.call_from_thread(self._update_status, "STATUS: READY")

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
        except Exception as exc:
            self.call_from_thread(self._log_msg, f"[bold #EF4444]LOGIN FAILED:[/] {exc}")

    def _ensure_log_handler(self) -> None:
        root = logging.getLogger()
        if hasattr(self, "_log_handler") and not any(isinstance(h, QwenTuiLogHandler) for h in root.handlers):
            root.addHandler(self._log_handler)

    def action_init_action(self) -> None:
        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            self._log_msg(f"[bold #10B981]INIT:[/] Workspace initialized in {Path.cwd()}")
        except Exception as exc:
            self._log_msg(f"[bold #EF4444]INIT ERROR:[/] {exc}")

    def action_reset_action(self) -> None:
        self.query_one("#input-prompt", Input).value = _default_prompt_value()
        self.query_one("#input-file", Input).value = _default_file_value()
        self.query_one("#input-output", Input).value = str(DEFAULT_OUTPUT)
        self._log_msg("[#908fa0]Form reset to default test paths.[/]")

    def _update_status(self, text: str) -> None:
        try:
            badge = self.query_one("#status-badge", Label)
            badge.update(text)
        except Exception:
            pass

    def _refresh_session_badge(self) -> None:
        """Check saved session validity asynchronously and update the badge."""
        try:
            badge = self.query_one("#session-badge", Label)
        except Exception:
            return
        if self._session is None:
            badge.update("SESSION: N/A")
            return
        badge.update("SESSION: CHECKING...")
        self._session_check_worker()

    @work(thread=True)
    def _session_check_worker(self) -> None:
        """Validate session in a worker thread so the UI never blocks."""
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
        except Exception:
            return
        badge.update("SESSION: VALID" if valid else "SESSION: EXPIRED")
        badge.set_classes("invalid" if not valid else "")

    def _request_quit(self) -> None:
        """Prompt for confirmation before quitting when a run is in progress."""
        if getattr(self, "_run_worker", None) is None:
            self.exit()
            return
        self._log_msg("[bold #F59E0B]WARNING:[/] Automation run in progress. Quit? (y/N)")
        self._log_msg("[#908fa0]Press Ctrl+Q again to force quit, Esc to cancel, or Cancel Run first.[/]")

    def action_request_quit(self) -> None:
        self._request_quit()

    def _log_msg(self, msg: str) -> None:
        try:
            log = getattr(self, "_log_view", None) or self.query_one("#log-view", RichLog)
            log.write(msg)
        except Exception:
            pass
