"""Chat console: prompt composer dispatch and per-slot send/cancel wiring.

Split from ``modules/tui/src/surface_tui_main_action.py`` so every handler
file stays on the AES surface complexity budget (AES406, 50 control-flow
statements). The combined alias re-exports this mixin for
:class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from typing import Any

from textual.css.query import NoMatches
from textual.widgets import Input


class _TuiChatLogHandlerMixin:
    """Chat console: prompt composer dispatch and per-slot send/cancel wiring."""

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
    start_add_session_login: Any

    _toggle_headless: Any

    # System-action workers live in _TuiSessionsWorkerMixin; declared here
    # so the router below type-checks and the AES scanner sees no
    # duplicate method definitions in this file.
    _run_doctor_worker: Any
    _run_update_worker: Any
    _last_delete_name: str

    # ── System Actions (Settings pane) ──────────────────────────────────

    def _send_composer(self, slot_id: int) -> None:
        """Echo the typed task into the transcript and dispatch it."""
        text = ""
        with contextlib.suppress(NoMatches):
            composer = self.query_one(f"#composer-{slot_id}", Input)
            text = composer.value.strip()
            if text:
                composer.value = ""
        if not text:
            with contextlib.suppress(Exception):
                self.notify(
                    "Type a task before sending.",
                    severity="warning",
                    title=f"Slot {slot_id}",
                )
            return
        attachment = ""
        # Issue #341: the attachment comes from the Attach pill's picker
        # state, not a composer field (the chat console has no file input).
        attachment = getattr(self, "_slot_attachments", {}).get(slot_id, "")
        self._append_chat_message(slot_id, "user", text, attachment=attachment)
        self._run_composer_slot(slot_id, text, attachment=attachment)


__all__ = ["_TuiChatLogHandlerMixin"]
