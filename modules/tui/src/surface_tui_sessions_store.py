"""Session and login workers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``@work(thread=True)``
workers that validate the stored session, load the account pool into the
Sessions screen, and run health checks. Splitting them from
:class:`~modules.tui.src.surface_tui_workers_store._TuiWorkersMixin` keeps that
file on slot/swarm execution and both files inside the AES surface complexity
budget.
Imported by :class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from typing import Any

from rich.markup import escape
from textual import work
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Label

from modules.shared.src.common.taxonomy_core_constant import SESSION_CHECK_TIMEOUT_SEC
from modules.shared.src.session.taxonomy_session_vo import SessionRequest


class _TuiSessionsWorkerMixin:
    """Mixin that owns session validation, badge, and account-pool workers."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _session: Any
    _session_manager: Any
    _session_check_timed_out: bool
    _last_session_state: str | None
    _session_check_timer: Any

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    _render_account_cards: Any
    _account_card: Any
    _sessions_cache: list[Any]
    query_one: Any
    notify: Any
    call_from_thread: Any
    set_timer: Any
    _ensure_log_handler: Any
    _jobs: Any
    _job_storage: Any
    _updater: Any
    _ensure_sessions_loaded: Any
    _sessions_loaded_once: bool
    #: Design-token map injected by :class:`QwenTuiApp` so this store-layer
    #: mixin does not import the view-layer ``THEME`` symbol.
    _theme: dict[str, str]
    #: Doctor-check runner callable injected by :class:`QwenTuiApp` so the
    #: store layer does not import the CLI command-layer ``run_doctor_checks``.
    _doctor_runner: Any

    def _force_sessions_refresh(self) -> None:
        """Reset the one-shot load guard and reload the account pool.

        ``_ensure_sessions_loaded`` skips the reload once
        ``_sessions_loaded_once`` is set, which is correct for nav-dock
        re-visits but wrong right after a login that mutated the pool. This
        helper clears the guard and re-runs the load.
        """
        self._sessions_loaded_once = False
        self._ensure_sessions_loaded()

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
        self._session_check_timer = self.set_timer(SESSION_CHECK_TIMEOUT_SEC, self._session_check_timeout)
        self._session_check_worker()

    def _session_check_timeout(self) -> None:
        if self._session_check_timed_out:
            return
        self._session_check_timed_out = True
        self._last_session_state = "TIMEOUT"
        msg = "Session check timed out — run 'qwen-web-arwaky doctor' for diagnostics."
        self._log_msg("[bold {}]WARNING:[/] {}".format(self._theme["warn"], msg))
        with contextlib.suppress(Exception):
            self.notify(msg, severity="warning", title="Session")

    @work(thread=True)
    def _session_check_worker(self) -> None:
        if self._session is None:
            self.call_from_thread(self._apply_session_state, "N/A")
            return
        try:
            from modules.shared.src.session.taxonomy_session_vo import SessionRequest

            response = self._session.execute(SessionRequest(verb="validate"))
            valid = response.valid
        except Exception:
            valid = False
        self.call_from_thread(self._apply_session_state, "VALID" if valid else "EXPIRED")

    def _apply_session_state(self, state: str) -> None:
        # Record the verdict and cancel the watchdog BEFORE the timer can fire.
        # The 60s timer is armed by _check_session; if the verdict callback
        # ever fails to reach us (e.g. a cross-thread dispatch dropped on a
        # busy app loop) the timer would fire later and print a spurious
        # "Session check timed out" even though the check already succeeded —
        # which is exactly the log the user saw: EVENT_LOGIN_VERIFIED, then
        # the timeout warning. Stopping it here keeps the two in step.
        if getattr(self, "_session_check_timer", None) is not None:
            self._session_check_timer.stop()
            self._session_check_timer = None
        self._session_check_timed_out = state == "TIMEOUT"
        self._last_session_state = state
        self._log_msg("[bold {}]SESSION:[/] {}".format(self._theme["muted"], state))

    # ── Session Pool Management ────────────────────────────────────────

    @work(thread=True, group="session-table", exclusive=True)
    def _refresh_sessions_table(self) -> None:
        """Load and display all sessions in the Sessions tab table.

        ``exclusive=True`` guards against a double-fire when this worker is
        scheduled from two paths in quick succession (e.g. ``_check_session``
        on mount plus a nav-dock click on the same event-loop tick). Without
        it the second invocation's callback would race the first into the DOM
        and ``query_one`` would see an inconsistent widget tree.
        """
        if not hasattr(self, "_session") or self._session is None:
            self.call_from_thread(self._log_msg, "[yellow]Session aggregate not available.[/]")
            return
        try:
            response = self._session.execute(SessionRequest(verb="list_sessions"))
            sessions = response.sessions or []
            total = len(sessions)
            healthy = sum(1 for s in sessions if s.is_healthy)
            limited = sum(1 for s in sessions if s.is_limited)

            def _update() -> None:
                rows = self.query_one("#session-rows", Vertical)
                rows.remove_children()
                if not sessions:
                    rows.mount(Label("No accounts registered.", classes="field-label"))
                else:
                    self._sessions_cache = list(sessions)
                    for position, s in enumerate(sessions, start=1):
                        rows.mount(self._account_card(s, position))
                # Keep the pane's three counters in step with the pool. The
                # strip is the pane's whole summary, so a repaint is the only
                # writer.
                with contextlib.suppress(NoMatches):
                    self.query_one("#session-metric-registered", Label).update(f"{total}")
                    self.query_one("#session-metric-active", Label).update(f"{healthy}")
                    self.query_one("#session-metric-expired", Label).update(f"{limited}")
                self._log_msg(
                    "[bold {}]SESSIONS:[/] Loaded {} sessions ({} healthy, {} limited).".format(
                        self._theme["ok"], total, healthy, limited
                    ),
                )

            # _refresh_sessions_table is @work(thread=True), so this worker runs
            # on a background thread and the dispatch below is a real
            # cross-thread hop. The outer try/except catches data-load errors
            # (load_pool, query_one on a table that is not yet mounted, etc.)
            # — NOT the app-thread call_from_thread ValueError, which is a
            # scheduling no-op, not a data error, and should not masquerade
            # as a session load failure.
            with contextlib.suppress(ValueError):
                # call_from_thread raises ValueError when the calling thread is
                # already the app thread (a scheduling no-op, not a data error).
                # Swallowing it here keeps "SESSION LOAD ERROR" reserved for
                # genuine load failures.
                self.call_from_thread(_update)
        except Exception as exc:
            # Only real data-load errors reach here. App-thread call_from_thread
            # scheduling errors are swallowed above so they do not print a
            # misleading "SESSION LOAD ERROR".
            self.call_from_thread(
                self._log_msg,
                "[bold {}]SESSION LOAD ERROR:[/] {}".format(self._theme["err"], escape(str(exc))),
            )

    # ── System Actions (Settings pane) ─────────────────────────────────

    @work(thread=True)
    def _run_doctor_worker(self) -> None:
        """Run the doctor diagnostic checks in a background thread."""
        self._log_msg("[bold {}]DOCTOR:[/] Running system diagnostics...".format(self._theme["accent_fg"]))
        try:
            doctor_runner = getattr(self, "_doctor_runner", None)
            if doctor_runner is None:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DOCTOR:[/] Doctor runner not injected.".format(self._theme["warn"]),
                )
                return
            checks = doctor_runner()
            failed = [c for c in checks if not c["passed"]]
            if failed:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DOCTOR:[/] {} check(s) failed.".format(self._theme["err"], len(failed)),
                )
                for c in failed:
                    self.call_from_thread(
                        self._log_msg,
                        "  ✗ {} — {}".format(escape(c["name"]), escape(c["detail"])),
                    )
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DOCTOR:[/] All checks passed. System is healthy.".format(self._theme["ok"]),
                )
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]DOCTOR ERROR:[/] {}".format(self._theme["err"], escape(str(exc))),
            )

    @work(thread=True)
    def _run_update_worker(self) -> None:
        """Run a self-update check in a background thread."""
        self._log_msg("[bold {}]UPDATE:[/] Checking for updates...".format(self._theme["accent_fg"]))
        updater = getattr(self, "_updater", None)
        if updater is None:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]UPDATE:[/] No updater injected — run 'qwa update --check' from the shell.".format(
                    self._theme["warn"]
                ),
            )
            return
        try:
            check = updater.check_update()
            if check.latest_version is None:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Could not reach version source ({}).".format(
                        self._theme["warn"], escape(str(check.error or "unknown"))
                    ),
                )
            elif check.update_available:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Update available: {} → {} — run 'qwa update' to upgrade.".format(
                        self._theme["ok"],
                        escape(check.current_version or "unknown"),
                        escape(check.latest_version or "latest"),
                    ),
                )
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Already up to date ({}).".format(
                        self._theme["ok"], escape(check.current_version or "unknown")
                    ),
                )
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]UPDATE ERROR:[/] {}".format(self._theme["err"], escape(str(exc))),
            )

    # ── Swarm engine readout ─────────────────────────────────────────────

    @work(thread=True)
    def _run_session_health_check(self) -> None:
        """Run health checks on all sessions via the session aggregate."""
        if not hasattr(self, "_session") or self._session is None:
            self.call_from_thread(self._log_msg, "[yellow]Session aggregate not available.[/]")
            return
        try:
            response = self._session.execute(SessionRequest(verb="check_health"))
            if response.error:
                raise RuntimeError(response.error)
            healthy_count = response.health_healthy or 0
            total = response.health_total or 0
            self.call_from_thread(
                self._log_msg,
                "[bold {}]HEALTH CHECK:[/] {}/{} sessions healthy.".format(self._theme["ok"], healthy_count, total),
            )
            self.call_from_thread(self._refresh_sessions_table)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]HEALTH CHECK ERROR:[/] {}".format(self._theme["err"], escape(str(exc))),
            )

    # ── Add Session Worker ──────────────────────────────────────────────

    def start_add_session_login(self, session_name: str) -> None:
        """Start the background worker to run headed browser login for a new session.

        Registers ``session_name`` in the pool by running the ``login`` session
        verb, which opens the headed browser and waits for a valid session.
        Logs the outcome to the event log and shows a success/error toast when
        the worker completes.
        """
        if getattr(self, "_session", None) is None:
            self._log_msg("[bold {}]ERROR:[/] Session orchestrator not available.".format(self._theme["err"]))
            return

        self._log_msg(
            "[bold {}]LAUNCHING BROWSER:[/] Please log in at chat.qwen.ai, then close the window.".format(
                self._theme["accent_fg"]
            )
        )
        self.notify(
            "Browser opened for login. Complete sign-in at chat.qwen.ai, then close the window.",
            title="Add Session",
            severity="information",
            timeout=10,
        )

        self._run_add_session_worker(session_name)

    @work(thread=True)
    def _run_add_session_worker(self, session_name: str) -> None:
        """Background worker that runs the headed browser login and validates the session."""
        try:
            response = self._session.execute(SessionRequest(verb="login", name=session_name))
            if response.valid and not response.error:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]SUCCESS:[/] Session '{}' saved at {}".format(
                        self._theme["ok"], escape(session_name), escape(str(response.profile_path or ""))
                    ),
                )
                self.call_from_thread(self.notify, f"Session '{session_name}' added successfully!", "success", 5)
                self.call_from_thread(self._refresh_sessions_table)
            else:
                error_msg = response.error or response.message or "Login failed"
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]LOGIN FAILED:[/] {}".format(self._theme["err"], escape(str(error_msg))),
                )
                self.call_from_thread(self.notify, f"Login failed: {error_msg}", "error", 8)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN ERROR:[/] {}".format(self._theme["err"], escape(str(exc))),
            )
            self.call_from_thread(self.notify, f"Login error: {exc}", "error", 8)


__all__ = ["_TuiSessionsWorkerMixin"]
