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

from modules.cli.src.surface_cli_tui_compose import JOBS_TABLE_ID
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
    _jobs: Any
    _job_storage: Any
    _updater: Any
    _ensure_sessions_loaded: Any
    _sessions_loaded_once: bool

    # ── Login worker ─────────────────────────────────────────────────────

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        self._log_msg("[bold {}]LOGIN…[/] authenticating a new session profile".format(THEME["accent"]))
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.execute_setup(SetupRequest())
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN RESULT:[/] {}".format(
                    THEME["ok"],
                    escape(str(res.error or res.message or res.profile_path or "")),
                ),
            )
            self.call_from_thread(self._check_session)
            # A login just registered a new session profile — the pool counts
            # and account cards on the Sessions pane are stale. Force a reload
            # so the REGISTERED/ACTIVE/LIMITED tiles and cards reflect the
            # account that was just added.
            self.call_from_thread(self._force_sessions_refresh)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN FAILED:[/] {}".format(THEME["err"], escape(str(exc))),
            )
        finally:
            self._login_in_flight = False

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
        # Record the verdict and cancel the watchdog BEFORE the timer can fire.
        # The 15s timer is armed by _check_session; if the verdict callback
        # ever fails to reach us (e.g. a cross-thread dispatch dropped on a
        # busy app loop) the timer would fire 15s later and print a spurious
        # "Session check timed out" even though the check already succeeded —
        # which is exactly the log the user saw: EVENT_LOGIN_VERIFIED, then
        # the timeout warning. Stopping it here keeps the two in step.
        if getattr(self, "_session_check_timer", None) is not None:
            self._session_check_timer.stop()
            self._session_check_timer = None
        self._session_check_timed_out = state == "TIMEOUT"
        self._last_session_state = state
        self._log_msg("[bold {}]SESSION:[/] {}".format(THEME["muted"], state))

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
        if not hasattr(self, "_session_manager") or self._session_manager is None:
            self.call_from_thread(self._log_msg, "[yellow]Session manager not available.[/]")
            return
        try:
            pool = self._session_manager.load_pool()
            sessions = pool.sessions
            total = pool.total_count
            healthy = sum(1 for s in sessions if s.is_healthy)
            limited = sum(1 for s in sessions if s.is_limited)

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
                self._render_account_cards(list(sessions))
                with contextlib.suppress(NoMatches):
                    self.query_one("#session-total", Label).update(f"{total}")
                    self.query_one("#session-healthy", Label).update(f"{healthy}")
                    self.query_one("#session-limited", Label).update(f"{limited}")
                # _update runs on the app thread only when _refresh_sessions_table
                # was called from the main thread; call_from_thread is the no-op
                # fast path in that case. It must NOT appear inside the callback
                # itself — calling it from the app thread raises ValueError and
                # surfaces as a spurious "SESSION LOAD ERROR" even though the
                # table rendered fine.
                self._log_msg(
                    "[bold {}]SESSIONS:[/] Loaded {} sessions ({} healthy, {} limited).".format(
                        THEME["ok"], total, healthy, limited
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
                "[bold {}]SESSION LOAD ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    # ── System Actions (Settings pane) ─────────────────────────────────

    @work(thread=True)
    def _run_doctor_worker(self) -> None:
        """Run the doctor diagnostic checks in a background thread."""
        self._log_msg("[bold {}]DOCTOR:[/] Running system diagnostics...".format(THEME["accent_fg"]))
        try:
            from modules.cli.src.surface_cli_doctor_command import run_doctor_checks

            checks = run_doctor_checks()
            failed = [c for c in checks if not c["passed"]]
            if failed:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DOCTOR:[/] {} check(s) failed.".format(THEME["err"], len(failed)),
                )
                for c in failed:
                    self.call_from_thread(
                        self._log_msg,
                        "  ✗ {} — {}".format(escape(c["name"]), escape(c["detail"])),
                    )
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]DOCTOR:[/] All checks passed. System is healthy.".format(THEME["ok"]),
                )
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]DOCTOR ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    @work(thread=True)
    def _run_update_worker(self) -> None:
        """Run a self-update check in a background thread."""
        self._log_msg("[bold {}]UPDATE:[/] Checking for updates...".format(THEME["accent_fg"]))
        updater = getattr(self, "_updater", None)
        if updater is None:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]UPDATE:[/] No updater injected — run 'qwa update --check' from the shell.".format(
                    THEME["warn"]
                ),
            )
            return
        try:
            check = updater.check_update()
            if check.latest_version is None:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Could not reach version source ({}).".format(
                        THEME["warn"], escape(str(check.error or "unknown"))
                    ),
                )
            elif check.update_available:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Update available: {} → {} — run 'qwa update' to upgrade.".format(
                        THEME["ok"],
                        escape(check.current_version or "unknown"),
                        escape(check.latest_version or "latest"),
                    ),
                )
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}]UPDATE:[/] Already up to date ({}).".format(
                        THEME["ok"], escape(check.current_version or "unknown")
                    ),
                )
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]UPDATE ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    @work(thread=True)
    def _run_jobs_cleanup(self) -> None:
        """Remove stale job records past their retention window (non-destructive for active jobs)."""
        self.call_from_thread(
            self._log_msg,
            "[bold {}]JOBS:[/] Cleaning up stale job records...".format(THEME["accent_fg"]),
        )
        jobs_storage = getattr(self, "_job_storage", None)
        if jobs_storage is None:
            self.call_from_thread(
                self.notify,
                "Job storage not available. Use 'qwa jobs cleanup' from the shell instead.",
                severity="warning",
            )
            return
        try:
            removed = jobs_storage.cleanup_stale_jobs()
            self.call_from_thread(
                self.notify,
                f"Removed {removed} stale job record(s). Running jobs are preserved.",
                severity="information",
            )
        except Exception as exc:
            self.call_from_thread(self.notify, f"Job cleanup failed: {exc}", severity="error")

    def _refresh_jobs_table(self) -> None:
        """Load and display recent jobs in the Settings pane's jobs table."""
        if getattr(self, "_jobs", None) is None:
            self.notify("Jobs aggregate not available in this container.", severity="warning")
            return
        self._refresh_jobs_table_worker()

    @work(thread=True, group="jobs-table", exclusive=True)
    def _refresh_jobs_table_worker(self) -> None:
        """Load recent jobs from the job storage and render the table."""
        # Generation guard: if a newer worker started, bail out before writing.
        gen = getattr(self, "_jobs_table_gen", 0) + 1
        self._jobs_table_gen = gen
        try:
            from modules.shared.src.taxonomy_jobs_vo import JobRequest

            response = self._jobs.execute(JobRequest(verb="list_jobs", limit=20))
            records = response.records or []

            def _update() -> None:
                # A newer worker started; this one is stale.
                if getattr(self, "_jobs_table_gen", 0) != gen:
                    return
                with contextlib.suppress(NoMatches):
                    table = self.query_one(f"#{JOBS_TABLE_ID}", DataTable)
                    table.clear()
                    table.add_columns("JOB ID", "STATUS", "INPUT", "DURATION", "COMPLETED")
                    for rec in records:
                        status = "RUNNING" if not rec.completed else ("FAILED" if rec.error else "DONE")
                        duration = f"{rec.duration_sec}s" if rec.duration_sec else "-"
                        completed_at = (rec.completed_at or "")[:19]
                        table.add_rows(
                            (
                                str(rec.job_id)[:30],
                                status,
                                str(rec.input_file or "-")[:30],
                                duration,
                                completed_at,
                            )
                        )
                self._log_msg(
                    "[bold {}]JOBS:[/] {} background job(s) listed.".format(THEME["ok"], len(records)),
                )

            with contextlib.suppress(ValueError):
                self.call_from_thread(_update)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]JOBS LOAD ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    # ── Swarm engine readout ─────────────────────────────────────────────

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
