"""Event handlers and keyboard-action methods for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing all Textual event callbacks
(``on_button_pressed``, ``on_select_changed``, ``on_input_changed``) and
action methods (``action_*``).
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Select, TabbedContent

from modules.cli.src.surface_cli_session_setup import ConfirmModal
from modules.cli.src.surface_cli_tui_components import FilePickerModal, HelpScreen
from modules.cli.src.surface_cli_tui_css import THEME


class _TuiHandlersMixin:
    """Mixin that owns all Textual event handlers and action bindings."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _target_field_for_picker: str | None
    _template_roles: set[str]
    _slot_workers: dict[int, Any]
    _NUM_SLOTS: int

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _run_slot: Any
    _cancel_slot: Any
    query_one: Any
    _log_msg: Any
    push_screen: Any
    _login_worker: Any
    _workspace: Any
    exit: Any
    _login_in_flight: bool
    call_from_thread: Any
    notify: Any

    # ── Widget event callbacks ───────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        for prefix, handler in (("btn-run-", self._run_slot), ("btn-cancel-", self._cancel_slot)):
            if button_id.startswith(prefix):
                handler(int(button_id.removeprefix(prefix)))
                return
        for field, picker in (("prompt", False), ("file", True), ("output", False)):
            prefix = f"btn-browse-{field}-"
            if button_id.startswith(prefix):
                slot_id = int(button_id.removeprefix(prefix))
                self._open_picker(f"input-{field}-{slot_id}", select_directories=picker)
                return

    def on_select_changed(self, event: Select.Changed) -> None:
        select_id = event.select.id or ""
        if not select_id.startswith("select-template-"):
            return
        slot_id = int(select_id.split("-")[-1])
        role = event.value
        if role is None:
            return
        with contextlib.suppress(NoMatches):
            prompt_input = self.query_one(f"#input-prompt-{slot_id}", Input)
            prompt_input.value = str(role)
            self._log_msg(
                f"[bold {THEME['bright']}]TEMPLATE:[/] Slot {slot_id} ← role '{escape(str(role))}'",
                slot_id,
            )
            # U8: optimistic existence hint when the picked value is a file path.
            if str(role) not in self._template_roles and not Path(str(role)).exists():
                self._log_msg(
                    f"[{THEME['warn']}]WARNING:[/] '{escape(str(role))}' is not a "
                    "known role and the file does not exist.",
                    slot_id,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """U6: keep the template Select in sync with manual path/role entry."""
        input_id = event.input.id or ""
        if not input_id.startswith("input-prompt-"):
            return
        slot_id = int(input_id.split("-")[-1])
        value = event.value.strip()
        with contextlib.suppress(NoMatches):
            select = self.query_one(f"#select-template-{slot_id}", Select)
            if value in self._template_roles:
                select.value = value
            elif select.value not in (None, Select.BLANK) and select.value != value:
                select.value = Select.BLANK

    # ── File picker ──────────────────────────────────────────────────────

    def _open_picker(self, target_input_id: str, select_directories: bool = False) -> None:
        # C3: capture the target id in the closure so concurrent picker
        # pushes cannot overwrite each other via shared instance state.
        captured_target = target_input_id
        return_focus_id = f"btn-browse-{target_input_id.removeprefix('input-')}"

        def _on_picked(path: str | None) -> None:
            if path and captured_target:
                with contextlib.suppress(NoMatches):
                    field = self.query_one(f"#{captured_target}", Input)
                    field.value = path

        self.push_screen(
            FilePickerModal(
                select_directories=select_directories,
                return_focus_id=return_focus_id,
            ),
            _on_picked,
        )

    # ── Tab navigation helpers ───────────────────────────────────────────

    def _get_active_slot_id(self) -> int:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            active_id = tabs.active or ""
            if active_id.startswith("tab-slot-"):
                return int(active_id.split("-")[-1])
        return 1

    # ── Keyboard actions ─────────────────────────────────────────────────

    def action_run_active_slot(self) -> None:
        self._run_slot(self._get_active_slot_id())

    def action_cancel_active_slot(self) -> None:
        """A8: cancel the currently focused slot from the keyboard (ctrl+x)."""
        self._cancel_slot(self._get_active_slot_id())

    def action_switch_tab_overview(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-overview"

    def _switch_to_slot(self, slot_id: int) -> None:
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = f"tab-slot-{slot_id}"

    def action_switch_tab_slot(self, slot_id: int) -> None:
        self._switch_to_slot(int(slot_id))

    def action_prev_slot(self) -> None:
        """A4: navigate to the previous slot tab (alt+left)."""
        current = self._get_active_slot_id()
        prev = current - 1 if current > 1 else self._NUM_SLOTS
        self._switch_to_slot(prev)

    def action_next_slot(self) -> None:
        """A4: navigate to the next slot tab (alt+right)."""
        current = self._get_active_slot_id()
        nxt = current + 1 if current < self._NUM_SLOTS else 1
        self._switch_to_slot(nxt)

    def action_show_help(self) -> None:
        """A4: push the keyboard-shortcut reference overlay."""
        self.push_screen(HelpScreen())

    def action_login_action(self) -> None:
        # U3: re-entrancy guard — one login flow at a time.
        if getattr(self, "_login_in_flight", False):
            self._log_msg(f"[bold {THEME['warn']}]WARNING:[/] Login already in progress.")
            return
        self._login_in_flight = True
        self._log_msg(f"[bold {THEME['accent']}]>>> Launching interactive session setup...[/]")
        self._login_worker()

    def action_init_action(self) -> None:
        """U8: trigger workspace initialization on a background thread."""
        self._log_msg(f"[bold {THEME['accent']}]>>> Initializing workspace...[/]")
        self._init_worker()

    @work(thread=True)
    def _init_worker(self) -> None:
        from modules.shared.src.taxonomy_core_vo import FilePath

        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            cwd = Path.cwd()
            self.call_from_thread(
                self._log_msg,
                f"[bold {THEME['ok']}]INIT:[/] Workspace initialized in {escape(str(cwd))}",
            )
            self.call_from_thread(self.notify, f"Workspace initialized in {cwd}", "information", 3)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                f"[bold {THEME['err']}]INIT ERROR:[/] {escape(str(exc))}",
            )

    def action_request_quit(self) -> None:
        import time

        active = [s for s, w in self._slot_workers.items() if w is not None]
        if not active:
            # A4: double-escape guard — require two Esc presses within 1s.
            now = time.monotonic()
            last = getattr(self, "_last_esc_time", 0.0)
            if now - last > 1.0:
                self._last_esc_time = now
                # A6: use notify for visibility regardless of active tab
                self.notify("Press Escape again within 1s to quit", timeout=1.5)
                self._log_msg(f"[{THEME['muted']}]Press Escape again within 1s to quit.[/]")
                return
            self.exit()
            return

        # U2: never quit silently while jobs are running.
        active_ids = ", ".join(str(s) for s in sorted(active))

        def _confirmed(confirmed: bool | None) -> None:
            if confirmed:
                for s in active:
                    self._cancel_slot(s)
                self.exit()

        self.push_screen(
            ConfirmModal(
                "Confirm Quit",
                f"{len(active)} automation job(s) are still running (Slots: {active_ids}).\n"
                "Quitting will cancel them. Browser processes will be stopped.",
                confirm_text="Quit Anyway",
            ),
            _confirmed,
        )


__all__ = ["_TuiHandlersMixin"]
