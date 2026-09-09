"""Reusable Textual components for the Obsidian Nebula TUI.

Kept separate from ``surface_cli_tui_app`` so the app surface stays thin
(AES406 SURFACE_ROLE: control-flow budget) while these components remain
independently testable.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label, Static

if TYPE_CHECKING:
    from modules.cli.src.surface_cli_tui_app import QwenTuiApp


class FilePickerModal(ModalScreen[str | None]):
    """Modal screen for visual file picking using DirectoryTree."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel"),
        Binding("ctrl+s", "select_current_folder", "Select Folder", show=False),
    ]

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

    def action_select_current_folder(self) -> None:
        if self._select_directories:
            self.dismiss(str(self._current_path))

    # A2: return focus to the invoking widget after dismissal.
    def on_dismiss(self) -> None:
        if self._return_focus_id:
            with contextlib.suppress(LookupError):
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

    @staticmethod
    def _truncate(text: str, limit: int = 200) -> str:
        """Truncate long log lines to prevent RichLog horizontal overflow."""
        return text if len(text) <= limit else text[: limit - 3] + "..."

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self._truncate(record.getMessage())
            name = record.name
            lvl = record.levelname

            # Build a rich.text.Text object directly — bypasses the Rich
            # markup parser entirely so dict reprs like {'status': 200} with
            # curly braces never get misinterpreted as markup syntax.
            text = Text()

            if record.levelno >= logging.ERROR:
                text.append(f"[{lvl}]", style=Style(bold=True, color="#EF4444"))
                text.append(f"[{name}]", style=Style(bold=True, color="#EF4444"))
                text.append(" ")
                text.append(msg, style="#EF4444")
            elif record.levelno >= logging.WARNING:
                text.append(f"[{lvl}]", style=Style(bold=True, color="#F59E0B"))
                text.append(f"[{name}]", style=Style(bold=True, color="#F59E0B"))
                text.append(" ")
                text.append(msg, style="#F59E0B")
            elif record.levelno >= logging.INFO:
                text.append(f"[{name}]", style=Style(bold=True, color="#3B82F6"))
                text.append(" ")
                text.append(msg, style="#d5e4fa")
            else:
                text.append(f"[{name}]", style="#64748B")
                text.append(" ")
                text.append(msg, style="#908fa0")

            slot_id: int | None = None
            if record.threadName and record.threadName.startswith("qwen_slot_worker_"):
                with contextlib.suppress(ValueError):
                    slot_id = int(record.threadName.split("_")[-1])

            with contextlib.suppress(RuntimeError):
                self._app.call_from_thread(self._app._log_msg, text, slot_id)
        except Exception:
            self.handleError(record)
