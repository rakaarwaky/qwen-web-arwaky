"""Nav dock, tab/slot navigation, log viewing, clipboard, and file picker.

Split from ``modules/tui/src/surface_tui_main_action.py`` so every handler
file stays on the AES surface complexity budget (AES406, 50 control-flow
statements). The combined alias re-exports this mixin for
:class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Label, TabbedContent

from modules.tui.src.surface_tui_component import (
    FilePickerModal,
    HelpScreen,
    QwenTuiRichLog,
)
from modules.tui.src.surface_tui_css_view import THEME


class _TuiNavLogHandlerMixin:
    """Nav dock, tab/slot navigation, log viewing, clipboard, and file picker."""

    """Mixin that owns all Textual event handlers and action bindings."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _target_field_for_picker: str | None
    _slot_workers: dict[int, Any]
    _NUM_SLOTS: int
    _run_swarm: Any
    _cancel_swarm: Any
    _sessions_cache: list[Any]
    _sessions_loaded_once: bool
    _session_row: int
    # Issue #341: per-slot attachment path chosen via the Attach pill.
    _slot_attachments: dict[int, str]

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _run_slot: Any
    _cancel_slot: Any
    _append_chat_message: Any
    _run_composer_slot: Any
    query: Any
    query_one: Any
    _log_swarm_msg: Any
    set_focus: Any
    _log_msg: Any
    copy_to_clipboard: Any
    push_screen: Any
    _workspace: Any
    exit: Any
    call_from_thread: Any
    _ensure_sessions_loaded: Any
    notify: Any
    _session: Any
    _session_manager: Any
    _refresh_sessions_table: Any
    _run_session_health_check: Any
    _render_account_cards: Any
    _jobs: Any
    _job_storage: Any
    _updater: Any
    _update_orchestrator: Any
    _setup: Any

    # Stubs for methods provided by _TuiSessionsWorkerMixin.
    start_add_session_login: Any

    _toggle_headless: Any

    # System-action workers live in _TuiSessionsWorkerMixin; declared here
    # so the router below type-checks and the AES scanner sees no
    # duplicate method definitions in this file.
    _run_doctor_worker: Any
    _run_update_worker: Any
    _last_delete_name: str

    # ── System Actions (Settings pane) ──────────────────────────────────

    def _get_active_slot_id(self) -> int:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            active_id = tabs.active or ""
            if active_id.startswith("tab-slot-"):
                return int(active_id.split("-")[-1])
        return 1

    def _refresh_nav_dock(self) -> None:
        """Update the bottom nav dock's active indicator to match the tab bar."""
        with contextlib.suppress(Exception):
            from textual.widgets import Button

            tabs = self.query_one(TabbedContent)
            active = tabs.active or ""
            overview_btn = self.query_one("#nav-overview", Button)
            login_btn = self.query_one("#nav-login", Button)
            chat_btn = self.query_one("#nav-chat", Button)
            swarm_btn = self.query_one("#nav-swarm", Button)
            settings_btn = self.query_one("#nav-settings", Button)
            # Reset all to inactive; then activate the one that matches. The
            # active rule must drop the inactive class too: both classes on one
            # button makes the later-defined inactive rule win.
            for btn in (overview_btn, login_btn, chat_btn, swarm_btn, settings_btn):
                btn.set_class(True, "nav-inactive")
                btn.set_class(False, "nav-active")
            active_btn = {
                "tab-overview": overview_btn,
                "tab-sessions": login_btn,
                "tab-swarm": swarm_btn,
                "tab-settings": settings_btn,
            }.get(active)
            if active.startswith("tab-slot-"):
                active_btn = chat_btn
            if active_btn is not None:
                active_btn.set_class(False, "nav-inactive")
                active_btn.set_class(True, "nav-active")

    def _nav_dock_go(self, button_id: str) -> None:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            if button_id == "nav-overview":
                tabs.active = "tab-overview"
            elif button_id == "nav-login":
                tabs.active = "tab-sessions"
                self._ensure_sessions_loaded()
            elif button_id == "nav-chat":
                active_id = tabs.active or ""
                tabs.active = active_id if active_id.startswith("tab-slot-") else "tab-slot-1"
            elif button_id == "nav-swarm":
                tabs.active = "tab-swarm"
            elif button_id == "nav-settings":
                self.action_switch_tab_settings()
                return
        self._refresh_nav_dock()

    def action_run_active_slot(self) -> None:
        """Run the currently focused slot from the keyboard (enter / ctrl+r)."""
        self._run_slot(self._get_active_slot_id())

    def action_cancel_active_slot(self) -> None:
        """A8: cancel the currently focused slot from the keyboard (ctrl+x)."""
        self._cancel_slot(self._get_active_slot_id())

    def action_copy_active_log(self) -> None:
        """Copy the currently visible log buffer to the system clipboard.

        Targets whichever log view belongs to the active tab: the overview
        log when the Overview tab is focused, the swarm log when the Swarm
        tab is focused, or the per-slot log view when a slot tab is active.
        """
        active_view: QwenTuiRichLog | None = None
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        active_key = self._get_active_slot_id()
        if active_key == 0:
            active_view = log_views.get(0)
        elif active_key == -1:
            active_view = log_views.get(-1)
        else:
            active_view = log_views.get(active_key)

        if active_view is None:
            self._log_msg("[yellow]No log view available to copy.[/]")
            return

        text = active_view.copy_text()
        if not text:
            self._log_msg("[yellow]Log buffer is empty — nothing to copy.[/]")
            return

        self.copy_to_clipboard(text)
        self.notify(f"Copied {len(text.splitlines())} log lines to clipboard", severity="information")

    def _copy_log_by_id(self, button_id: str) -> None:
        """Copy the log view associated with a copy button on the Overview/Swarm tab."""
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        view = log_views.get(0) if button_id == "btn-copy-log" else log_views.get(-1)
        if view is None:
            self._log_msg("[yellow]No log view available to copy.[/]")
            return
        self._copy_rich_log(view)

    def _copy_slot_log(self, slot_id: int) -> None:
        """Copy whichever of the slot's two log buffers is on screen."""
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        system_views: dict[Any, Any] = getattr(self, "_system_log_views", {})
        view = log_views.get(slot_id)
        system_view = system_views.get(slot_id)
        if view is not None and not view.display:
            view = None
        if system_view is not None and not system_view.display:
            system_view = None
        target = view or system_view
        if target is None:
            self._log_msg(f"[yellow]Slot {slot_id} log view not found.[/]")
            return
        self._copy_rich_log(target)

    def _copy_rich_log(self, view: QwenTuiRichLog) -> None:
        text = view.copy_text()
        if not text:
            self._log_msg("[yellow]Log buffer is empty — nothing to copy.[/]")
            return
        self.copy_to_clipboard(text)
        self.notify(f"Copied {len(text.splitlines())} log lines to clipboard", severity="information")

    def action_switch_tab_overview(self) -> None:
        """Switch to the Overview tab (alt+0)."""
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-overview"
        self._refresh_nav_dock()

    def action_switch_tab_swarm(self) -> None:
        """Switch to the Swarm tab (ctrl+alt+s)."""
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-swarm"
        self._refresh_nav_dock()

    def action_switch_tab_settings(self) -> None:
        """Switch to the Settings tab (ctrl+comma).

        The pane carries the runtime-override card and nothing else, so
        moving the tab is the whole switch.
        """
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-settings"
        self._refresh_nav_dock()

    def _switch_to_slot(self, slot_id: int) -> None:
        """Show a slot's tab and carry the keyboard focus into it.

        Clicking a pill focuses that pill, and Textual reacts to a focus
        landing in a pane by making THAT pane the active tab — which undid
        the switch and sent the console back to the slot the click came from.
        Moving the focus into the new pane keeps the tab and the focus in
        step, so one click lands and the keyboard follows.
        """
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            tab_id = f"tab-slot-{slot_id}"
            tabs.active = tab_id
            pane = tabs.get_pane(tab_id)
            focusable = [widget for widget in pane.query("*") if widget.focusable]
            self.set_focus(focusable[0] if focusable else None, scroll_visible=False)
        self._refresh_nav_dock()

    def _show_slot_log(self, slot_id: int, show_system: bool) -> None:
        """Swap a chat console between the slot's Event log and System log.

        The two share one panel, so exactly one view stays visible and only
        the pressed button keeps the active fill.
        """
        with contextlib.suppress(NoMatches):
            self.query_one(f"#log-view-{slot_id}", QwenTuiRichLog).display = not show_system
            self.query_one(f"#log-view-{slot_id}-system", QwenTuiRichLog).display = show_system
        with contextlib.suppress(NoMatches):
            event_btn = self.query_one(f"#btn-slot-event-{slot_id}", Button)
            system_btn = self.query_one(f"#btn-slot-system-{slot_id}", Button)
            event_btn.set_class(show_system, "seg-active")
            system_btn.set_class(not show_system, "seg-active")

    def action_switch_tab_slot(self, slot_id: int) -> None:
        """Switch to the tab of *slot_id* (alt+1..9, ctrl+alt+0..9)."""
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
        self.push_screen(HelpScreen(self._NUM_SLOTS))

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

    def _open_attachment_picker(self, slot_id: int) -> None:
        """Open the folder/file picker for the Attach pill (issue #341).

        The chat console has no attachment input field anymore, so the picked
        path is stored in the app's per-slot attachment state and rendered in
        the slot's file indicator instead of being written into an Input.
        """
        return_focus_id = f"btn-pill-attach-{slot_id}"

        def _on_picked(path: str | None) -> None:
            if not path:
                return
            self._slot_attachments[slot_id] = path
            with contextlib.suppress(NoMatches):
                indicator = self.query_one(f"#file-indicator-{slot_id}", Label)
                indicator.update(f"📎 {_attachment_label(path)}")
                indicator.display = True
            self._log_msg(
                "[bold {}]ATTACH:[/] Slot {} ← {}".format(THEME["ok"], slot_id, escape(str(Path(path)))),
                slot_id,
            )

        self.push_screen(
            FilePickerModal(
                select_directories=True,
                return_focus_id=return_focus_id,
            ),
            _on_picked,
        )


__all__ = ["_TuiNavLogHandlerMixin"]

#: Attachment types the file uploader accepts; a folder compiles to its
#: own markdown. A file that matches none of these is sent as-is and the
#: Qwen UI will reject it with its own type error.
_ATTACHMENT_TYPES: frozenset[str] = frozenset(
    {
        "txt",
        "md",
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "csv",
        "json",
        "yaml",
        "yml",
        "py",
        "js",
        "ts",
        "go",
        "rs",
        "java",
        "c",
        "cpp",
        "html",
        "css",
        "xml",
        "sh",
        "toml",
    }
)


def _attachment_label(path: str) -> str:
    """Display label for a picked attachment: folder or <type> file."""
    p = Path(path)
    if p.is_dir():
        return f"FOLDER: {p.name}"
    suffix = p.suffix.lstrip(".").lower()
    if not suffix:
        return p.name
    if suffix in _ATTACHMENT_TYPES:
        return f"<{suffix.upper()}> {p.name}"
    return f"{p.name} (unsupported type: {suffix})"
