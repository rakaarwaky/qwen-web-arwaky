"""Session and login workers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``@work(thread=True)``
workers that validate the stored session, load the account pool into the
Sessions screen, and run health checks. Splitting them from
:class:`~modules.cli.src.surface_cli_tui_workers._TuiWorkersMixin` keeps that
file on slot/swarm execution and both files inside the AES surface complexity
budget.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from typing import Any

from rich.markup import escape
from textual import work
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label

from modules.cli.src.surface_cli_tui_css import THEME
from modules.shared.src.taxonomy_setup_vo import SetupRequest


class _TuiSessionsWorkerMixin:
    """Mixin that owns session validation, badge, and account-pool workers."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _setup: Any
    _session: Any
    _session_manager: Any
    _session_check_timed_out: bool
    _last_session_state: str | None
    _login_in_flight: bool
    _session_check_timer: Any

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    _render_account_cards: Any
    query_one: Any
    notify: Any
    call_from_thread: Any
    set_timer: Any
    _ensure_log_handler: Any

    # ── Login worker ─────────────────────────────────────────────────────

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        self._log_msg("[bold {}]LOGIN…[/] authenticating a new session profile".format(THEME["accent"]))
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.execute(SetupRequest())
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN RESULT:[/] {}".format(
                    THEME["ok"],
                    escape(str(res.error or res.message or res.profile_path or "")),
                ),
            )
            self.call_from_thread(self._check_session)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN FAILED:[/] {}".format(THEME["err"], escape(str(exc))),
            )
        finally:
            self._login_in_flight = False

    # ── Session validation ───────────────────────────────────────────────

    def _check_session(self) -> None:
        """Validate the stored session and report the verdict to the log.

        The Overview banner carries only the active-account count and the
        routed model, so the verdict lands in the System Event Log and in
        ``_last_session_state`` (read by the sessions screen and by doctor)
        instead of a dedicated badge widget.
        """
        self._session_check_timed_out = False
        timer = getattr(self, "_session_check_timer", None)
        if timer is not None:
            timer.stop()
        self._session_check_timer = self.set_timer(15.0, self._session_check_timeout)
        self._session_check_worker()

    def _session_check_timeout(self) -> None:
        if self._session_check_timed_out:
            return
        self._session_check_timed_out = True
        self._last_session_state = "TIMEOUT"
        msg = "Session check timed out — run 'qwen-web-arwaky doctor' for diagnostics."
        self._log_msg("[bold {}]WARNING:[/] {}".format(THEME["warn"], msg))
        with contextlib.suppress(Exception):
            self.notify(msg, severity="warning", title="Session")

    @work(thread=True)
    def _session_check_worker(self) -> None:
        if self._session is None:
            self.call_from_thread(self._apply_session_state, "N/A")
            return
        try:
            from modules.shared.src.taxonomy_session_vo import SessionRequest

            response = self._session.execute(SessionRequest(verb="validate"))
            valid = response.valid
        except Exception:
            valid = False
        self.call_from_thread(self._apply_session_state, "VALID" if valid else "EXPIRED")

    def _apply_session_state(self, state: str) -> None:
        self._last_session_state = state
        self._log_msg("[bold {}]SESSION:[/] {}".format(THEME["muted"], state))
        # Cancel the timeout timer when the worker completes. Without this, a
        # 15s timer can fire after the verdict lands and overwrite it.
        if getattr(self, "_session_check_timer", None) is not None:
            self._session_check_timer.stop()
            self._session_check_timer = None

    # ── Session Pool Management ────────────────────────────────────────

    @work(thread=True)
    def _refresh_sessions_table(self) -> None:
        """Load and display all sessions in the Sessions tab table."""
        if not hasattr(self, "_session_manager") or self._session_manager is None:
            self.call_from_thread(self._log_msg, "[yellow]Session manager not available.[/]")
            return
        try:
            pool = self._session_manager.load_pool()
            sessions = pool.sessions

            def _update() -> None:
                table = self.query_one("#sessions-table", DataTable)
                table.clear()
                table.add_columns("ID", "Name", "Status", "Last Used", "Path")
                table.add_rows(
                    (
                        s.session_id,
                        s.name,
                        s.status.value,
                        s.last_used.strftime("%Y-%m-%d %H:%M") if s.last_used else "Never",
                        str(s.path),
                    )
                    for s in sessions
                )
                total = pool.total_count
                healthy = sum(1 for s in sessions if s.is_healthy)
                limited = sum(1 for s in sessions if s.is_limited)
                self._render_account_cards(list(sessions))
                with contextlib.suppress(NoMatches):
                    self.query_one("#session-total", Label).update(f"{total}")
                    self.query_one("#session-healthy", Label).update(f"{healthy}")
                    self.query_one("#session-limited", Label).update(f"{limited}")
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]SESSIONS:[/] Loaded {} sessions ({} healthy, {} limited).".format(
                        THEME["ok"], total, healthy, limited
                    ),
                )

            self.call_from_thread(_update)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]SESSION LOAD ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    @work(thread=True)
    def _run_session_health_check(self) -> None:
        """Run health checks on all sessions."""
        if not hasattr(self, "_session_manager") or self._session_manager is None:
            self.call_from_thread(self._log_msg, "[yellow]Session manager not available.[/]")
            return
        try:
            from modules.session.src.capabilities_session_health_checker import SessionHealthChecker

            results = SessionHealthChecker(timeout_seconds=10).check_pool_sync(
                self._session_manager.load_pool(),
                self._session_manager,
            )
            healthy_count = sum(1 for _, h in results if h)
            self.call_from_thread(
                self._log_msg,
                "[bold {}]HEALTH CHECK:[/] {}/{} sessions healthy.".format(THEME["ok"], healthy_count, len(results)),
            )
            self.call_from_thread(self._refresh_sessions_table)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]HEALTH CHECK ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )


__all__ = ["_TuiSessionsWorkerMixin"]
