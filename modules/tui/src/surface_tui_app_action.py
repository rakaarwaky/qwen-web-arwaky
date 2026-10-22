"""System actions, workspace init, session setup/login, quit guard.

Split from ``modules/tui/src/surface_tui_main_action.py`` so every handler
file stays on the AES surface complexity budget (AES406, 50 control-flow
statements). The combined alias re-exports this mixin for
:class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import work

from modules.tui.src.surface_tui_component import (
    AddSessionModal,
    ConfirmModal,
)
from modules.tui.src.surface_tui_css_view import THEME


class _TuiAppHandlerMixin:
    """System actions, workspace init, legacy session setup/login, quit guard."""

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

    # ── System Actions (Settings pane) ──────────────────────────────────

    def _system_action_pressed(self, button_id: str) -> None:
        """Route Settings-pane system-action button presses."""
        # @work(thread=True) returns a Worker; the router type must allow
        # handlers that return any object (Worker or None for sync handlers).
        router: dict[str, Callable[[], Any]] = {
            "btn-tui-doctor": self._run_doctor_worker,
            "btn-tui-update": self._run_update_worker,
        }
        handler = router.get(button_id)
        if handler is None:
            # Unknown button IDs are silently swallowed by the TUI; log a
            # warning so a forgotten compose-side button is not a dead code path.
            self._log_msg(f"[bold {THEME['warn']}]WARNING:[/] Unknown system-action button: {button_id!r}")
            return
        handler()

    def action_login_action(self) -> None:
        """Open the session name dialog, then run the headed browser login."""
        self.action_session_add_new()

    def action_init_action(self) -> None:
        """U8: trigger workspace initialization on a background thread."""
        self._log_msg("[bold {}]>>> Initializing workspace...[/]".format(THEME["accent_fg"]))
        self._init_worker()

    def action_session_add_new(self) -> None:
        """a: add a new session — opens name dialog then starts headed browser login."""
        if not hasattr(self, "_session_manager") or self._session_manager is None:
            self._log_msg("[yellow]Session manager not available.[/]")
            return
        self.push_screen(
            AddSessionModal(),
            self._on_add_session_name,
        )

    def _on_add_session_name(self, session_name: str | None) -> None:
        """Callback when AddSessionModal returns a session name."""
        if not session_name:
            self._log_msg("[dim]Add session cancelled.[/]")
            return
        self._log_msg("[bold {}]>>> Starting login for session '{}'...[/]".format(THEME["accent_fg"], session_name))
        # Delegate to the sessions worker mixin
        self.start_add_session_login(session_name)

    @work(thread=True)
    def _init_worker(self) -> None:
        from modules.shared.src.common.taxonomy_core_vo import FilePath

        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            cwd = Path.cwd()
            self.call_from_thread(
                self._log_msg,
                "[bold {}]INIT:[/] Workspace initialized in {}".format(THEME["ok"], escape(str(cwd))),
            )
            self.call_from_thread(self.notify, f"Workspace initialized in {cwd}", "information", 3)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]INIT ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    def action_request_quit(self) -> None:
        """Quit, requiring confirmation when jobs run or a double-Esc when idle."""

        active = [s for s, w in self._slot_workers.items() if w is not None]
        if not active:
            # A4: double-escape guard — require two Esc presses within 2s.
            now = time.monotonic()
            last = getattr(self, "_last_esc_time", 0.0)
            if now - last > 2.0:
                self._last_esc_time = now
                # A6: use notify for visibility regardless of active tab
                self.notify("Press Escape again within 2s to quit", timeout=3.0)
                self._log_msg("[{}]Press Escape again within 2s to quit.[/]".format(THEME["muted"]))
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
                confirm_label="Quit and Cancel Jobs",
            ),
            _confirmed,
        )


__all__ = ["_TuiAppHandlerMixin"]
