"""Sessions pane: account-card actions, delete confirmation flow, pool loading,

Split from ``modules/tui/src/surface_tui_main_action.py`` so every handler
file stays on the AES surface complexity budget (AES406, 50 control-flow
statements). The combined alias re-exports this mixin for
:class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from typing import Any

from rich.markup import escape
from textual import work
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, TabbedContent

from modules.tui.src.surface_tui_component import (
    ConfirmModal,
)
from modules.tui.src.surface_tui_css_view import THEME


class _TuiSessionsHandlerMixin:
    """Sessions pane: account-card actions, delete confirmation flow, pool loading,."""

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
    action_session_add_new: Any
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

    def _account_button_pressed(self, action: str, position: int) -> None:
        """Handle an action on the Sessions pane's account card at *position*."""
        cache: list[Any] = getattr(self, "_sessions_cache", [])
        session = cache[position - 1] if 0 < position <= len(cache) else None
        name = str(getattr(session, "name", "") or f"session {position}")
        if action == "refresh":
            # Refresh re-loads the pool from disk and repaints the row.
            self._log_msg("[bold {}]REFRESH:[/] Reloading session pool.".format(THEME["accent_fg"]))
            self._refresh_sessions_table()
            return
        if action == "health":
            # The pool health check is the same probe the CLI 'session health'
            # verb runs, so one card's test icon runs it rather than inventing
            # a single-session result from the last stored state.
            self._log_msg("[bold {}]TEST:[/] Checking connection for {}.".format(THEME["accent_fg"], escape(name)))
            self._run_session_health_check()
            return
        # Delete drops the stored auth session and its profile. That is an
        # approved-only operation: the confirm modal guards it, and the
        # worker runs the same logic as 'qwa session remove'.
        self._confirm_delete_session(name)

    def _confirm_delete_session(self, name: str) -> None:
        """Ask for confirmation before deleting a session from the pool."""
        self._last_delete_name = name
        self.push_screen(
            ConfirmModal(
                "Delete Session",
                f"Delete '{name}' from the pool and remove its browser profile?\n"
                "This cannot be undone without re-logging in.",
                confirm_label="Delete",
            ),
            self._run_delete_session,
        )

    @work(thread=True)
    def _run_delete_session(self, confirmed: bool) -> None:
        """Run the session delete in a background thread.

        Mirrors the CLI 'session remove' command: remove the pool entry,
        then delete the Chromium profile (the profile delete runs through
        SessionManager.delete_session_profile which carries all the
        path-safety guards).
        """
        if not confirmed:
            return
        manager = getattr(self, "_session_manager", None)
        cache: list[Any] = getattr(self, "_sessions_cache", [])
        if manager is None or not cache:
            self.call_from_thread(self._log_msg, "[yellow]Session manager not available.[/]")
            return
        # Resolve the captured name against the current pool so a stale card
        # (re-rendered while the modal was up) can't delete the wrong session.
        name = str(getattr(self, "_last_delete_name", ""))
        session = next((s for s in cache if str(getattr(s, "name", "")) == name), None)
        if session is None:
            self.call_from_thread(self._log_msg, "[yellow]Session no longer in pool — nothing to delete.[/]")
            return
        try:
            if not manager.remove_session(session.session_id):
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DELETE:[/] Could not remove '{}' from the pool.".format(THEME["err"], escape(name)),
                )
                return
            try:
                manager.delete_session_profile(session.path)
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DELETE:[/] Removed '{}' from pool and deleted its profile.".format(
                        THEME["ok"], escape(name)
                    ),
                )
            except Exception as exc:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DELETE:[/] Pool entry removed, profile kept: {}.".format(THEME["warn"], escape(str(exc))),
                )
            self.call_from_thread(self._refresh_sessions_table)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]DELETE ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    def _ensure_sessions_loaded(self) -> None:
        """Fetch the account pool the first time the Sessions pane is opened."""
        if getattr(self, "_sessions_loaded_once", False):
            return
        if getattr(self, "_session_manager", None) is None:
            return
        self._sessions_loaded_once = True
        self._refresh_sessions_table()

    def _sessions_active(self) -> bool:
        """Whether the Sessions pane is the visible tab."""
        try:
            tabs = self.query_one(TabbedContent)
        except NoMatches:
            return False
        return bool(tabs.active == "tab-sessions")

    def _session_row_index(self) -> int:
        """0-based index of the currently selected row, or -1 when none."""
        return int(getattr(self, "_session_row", -1))

    def _move_session_row(self, delta: int) -> None:
        """Move the selected row up/down and highlight it (problem 4)."""
        with contextlib.suppress(NoMatches):
            rows = self.query_one("#session-rows", Vertical)
            row_widgets = [w for w in rows.children if w.has_class("session-row")]
        if not row_widgets:
            return
        n = len(row_widgets)
        cur = self._session_row_index()
        new = min(max(cur + delta, 0), n - 1)
        for i, w in enumerate(row_widgets):
            w.set_class(new == i, "session-row-selected")
        self._session_row = new
        w = row_widgets[new]
        with contextlib.suppress(NoMatches):
            first_btn = w.query_one(Button)
            first_btn.focus()

    def action_sessions_up(self) -> None:
        """↑: previous session row (only on the Sessions pane)."""
        if self._sessions_active():
            self._move_session_row(-1)

    def action_sessions_down(self) -> None:
        """↓: next session row (only on the Sessions pane)."""
        if self._sessions_active():
            self._move_session_row(1)

    def action_session_add(self) -> None:
        """a: add a new session — same as the ADD SESSION button."""
        self.action_session_add_new()

    def action_session_refresh(self) -> None:
        """r: reload the pool (problem 6 / req C)."""
        self._refresh_sessions_table()

    def action_session_edit(self) -> None:
        """e: run the health check on the selected row (or the whole pool)."""
        idx = self._session_row_index()
        if idx >= 0:
            self._account_button_pressed("health", idx + 1)
        else:
            self._run_session_health_check()

    def action_session_delete(self) -> None:
        """d/Delete: delete the selected row's session, guarded by a modal."""
        idx = self._session_row_index()
        if idx < 0:
            self._log_msg("[dim]No session selected — press ↑/↓ first.[/]")
            return
        self._account_button_pressed("delete", idx + 1)


__all__ = ["_TuiSessionsHandlerMixin"]
