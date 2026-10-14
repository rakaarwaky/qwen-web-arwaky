"""Swarm screen: start/cancel routing and event/system log toggle.

Split from ``modules/tui/src/surface_tui_main_handlers.py`` so every handler
file stays on the AES surface complexity budget (AES406, 50 control-flow
statements). The combined alias re-exports this mixin for
:class:`~modules.tui.src.surface_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from typing import Any

from textual.css.query import NoMatches
from textual.widgets import Button

from modules.tui.src.surface_tui_components import (
    QwenTuiRichLog,
)
from modules.tui.src.surface_tui_css import THEME


class _TuiSwarmHandlerMixin:
    """Swarm screen: start/cancel routing and event/system log toggle."""

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
    _open_picker: Any
    start_add_session_login: Any

    _toggle_headless: Any

    # System-action workers live in _TuiSessionsWorkerMixin; declared here
    # so the router below type-checks and the AES scanner sees no
    # duplicate method definitions in this file.
    _run_doctor_worker: Any
    _run_update_worker: Any
    _last_delete_name: str

    # ── System Actions (Settings pane) ──────────────────────────────────

    def _swarm_button_pressed(self, button_id: str) -> None:
        """Route Swarm-screen button presses to the right handler."""
        if button_id == "btn-swarm-start":
            self._run_swarm()
        elif button_id == "btn-swarm-cancel":
            self._cancel_swarm()
        elif button_id == "btn-browse-swarm-file":
            self._open_picker("input-swarm-file", select_directories=True)
        elif button_id in ("btn-swarm-event", "btn-swarm-system"):
            self._show_swarm_log(button_id == "btn-swarm-system")
        elif button_id == "btn-clear-swarm-log":
            self._clear_swarm_log()

    def _show_swarm_log(self, show_system: bool) -> None:
        """Switch the Swarm tab between the Event log and the System log.

        The mockup presents these as a segmented toggle over one panel, so
        exactly one of the two RichLog views stays visible and the toggle
        buttons carry matching active/inactive styling.
        """
        with contextlib.suppress(NoMatches):
            event_log = self.query_one("#log-view-swarm", QwenTuiRichLog)
            system_log = self.query_one("#log-view-swarm-system", QwenTuiRichLog)
            event_log.display = not show_system
            system_log.display = show_system
        with contextlib.suppress(NoMatches):
            event_btn = self.query_one("#btn-swarm-event", Button)
            system_btn = self.query_one("#btn-swarm-system", Button)
            # Add/remove one class at a time. set_classes() would also drop
            # the -style-default class that Textual's own Button CSS hangs
            # its default rendering off, leaving the button unstyled.
            event_btn.set_class(not show_system, "toggle-active")
            event_btn.set_class(show_system, "toggle-inactive")
            system_btn.set_class(show_system, "toggle-active")
            system_btn.set_class(not show_system, "toggle-inactive")

    def _clear_swarm_log(self) -> None:
        """Empty whichever Swarm log view is currently on screen."""
        with contextlib.suppress(NoMatches):
            system_visible = self.query_one("#log-view-swarm-system", QwenTuiRichLog).display
            view = self.query_one("#log-view-swarm-system" if system_visible else "#log-view-swarm", QwenTuiRichLog)
            view.clear()
            self._log_swarm_msg(
                "[{}]Swarm log cleared.[/]".format(THEME["muted"]),
            )


__all__ = ["_TuiSwarmHandlerMixin"]
