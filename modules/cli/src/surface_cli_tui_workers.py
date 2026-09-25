"""Background workers and slot execution logic for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing all ``@work(thread=True)``
workers, slot run/cancel/finalise cycle, session badge refresh, and login.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path
from typing import Any, cast

from rich.markup import escape
from textual import work
from textual.app import ScreenStackError
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input, Label, LoadingIndicator, Switch

from modules.cli.src.surface_cli_tui_css import THEME
from modules.shared.src.taxonomy_core_vo import AppConfig, FilePath, HeadlessFlag, PromptText, SlotInputValue
from modules.shared.src.utility_core_response import detect_processing_failure

# A badge write can land while the app is tearing down: the worker thread's
# ``call_from_thread`` is queued on the event loop and keeps running after the
# screen is popped (``ScreenStackError``) or the badge is unmounted
# (``NoMatches``). Neither is a subclass of ``LookupError``/``AttributeError``,
# so catching only those let the exception escape as an app crash. There is
# nothing left to display in that window — return quietly instead.
_BADGE_UNAVAILABLE: tuple[type[BaseException], ...] = (
    NoMatches,
    ScreenStackError,
    LookupError,
    AttributeError,
)


class _TuiWorkersMixin:
    """Mixin that owns slot execution, session-check, and login workers."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _slot_workers: dict[int, Any]
    _slot_stats: dict[int, dict[str, Any]]
    _slot_config: Any
    _attachment: Any
    _file_only: Any
    _setup: Any
    _session: Any
    _swarm: Any
    _swarm_id: str | None
    _swarm_pending_input: Path | None
    _confirm_or_start_swarm: Any
    _session_check_timed_out: bool
    _last_session_state: str | None
    _login_in_flight: bool
    _slot_generation: dict[int, int]
    _slot_cancel_events: dict[int, threading.Event]

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    query_one: Any
    notify: Any
    _set_slot_tab_title: Any
    _truncate_name: Any
    _update_slot_status: Any
    _update_table_row: Any
    _refresh_metrics: Any
    _format_status: Any
    _format_event_status: Any
    call_from_thread: Any
    set_timer: Any
    set_interval: Any
    _ensure_log_handler: Any
    push_screen: Any
    _session_check_timer: Any
    _render_swarm_snapshot: Any

    # ── Slot run / cancel ────────────────────────────────────────────────

    def _run_slot(self, slot_id: int) -> None:
        if self._slot_workers.get(slot_id) is not None:
            self._log_msg("[bold {}]WARNING:[/] Slot {} already running.".format(THEME["warn"], slot_id), slot_id)
            with contextlib.suppress(Exception):
                self.notify(f"Slot {slot_id} is already running.", severity="warning", title=f"Slot {slot_id}")
            return

        try:
            prompt_val = self.query_one(f"#input-prompt-{slot_id}", Input).value
            file_val = self.query_one(f"#input-file-{slot_id}", Input).value
            out_val = self.query_one(f"#input-output-{slot_id}", Input).value
            headless_val = self.query_one(f"#switch-headless-{slot_id}", Switch).value
        except Exception as exc:
            # U1: a user-initiated action must never fail silently.
            msg = f"Could not read Slot {slot_id} inputs: {exc}"
            self._log_msg("[bold {}]ERROR:[/] {}".format(THEME["err"], escape(msg)), slot_id)
            with contextlib.suppress(Exception):
                self.notify(msg, severity="error", title=f"Slot {slot_id}")
            return

        plan = self._slot_config.resolve_slot_run_plan(
            PromptText(prompt_val),
            PromptText(file_val),
            cast(FilePath, out_val),
            HeadlessFlag(headless_val),
        )
        if isinstance(plan, SlotInputValue):
            msg = "[bold {}]ERROR:[/] {} (Slot {})".format(THEME["err"], escape(str(plan.message)), slot_id)
            self._log_msg(msg, slot_id)
            self._log_msg(msg)
            with contextlib.suppress(Exception):
                self.notify(str(plan.message), severity="error", title=f"Slot {slot_id}")
            return

        cfg: AppConfig = plan.config
        p_name = plan.prompt_path.name

        # AR-2/FE-1: create a per-slot cancel event so cancelling one slot
        # never touches another slot's in-flight browser context.
        self._slot_cancel_events[slot_id] = threading.Event()

        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(p_name)} ▶")
        with contextlib.suppress(NoMatches):
            self.query_one(f"#btn-retry-{slot_id}").display = False
        self._update_slot_status(slot_id, self._format_status("RUNNING", "badge"))
        self._slot_stats[slot_id] = {
            "status": "RUNNING",
            "file": p_name,
            "duration": 0.0,
            "event": "EVENT_WEB_LOADED",
            "_start_perf": time.perf_counter(),
        }
        self._update_table_row(slot_id, self._format_status("RUNNING", "table"), p_name, "running…")
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_slot_worker(slot_id, cfg)

    def _cancel_slot(self, slot_id: int) -> None:
        worker = self._slot_workers.get(slot_id)
        if worker is None:
            self._log_msg("[{}]No run active in Slot {}.[/]".format(THEME["muted"], slot_id), slot_id)
            return
        # U2: confirm before cancelling runs older than 30 seconds
        stats = self._slot_stats.get(slot_id, {})
        start_perf = stats.get("_start_perf", 0.0)
        elapsed = time.perf_counter() - start_perf if start_perf else 0.0
        if elapsed > 30:

            def _on_confirm(confirmed: bool | None) -> None:
                # Issue #331: the modal can be confirmed after the original
                # run already finished and a NEW run started in the same
                # slot. Only cancel when the slot still belongs to the exact
                # worker the modal was opened for (object identity), never a
                # successor run the user did not intend to stop.
                if confirmed and self._slot_workers.get(slot_id) is worker:
                    self._do_cancel_slot(slot_id)

            from modules.cli.src.surface_cli_tui_components import ConfirmModal

            self.push_screen(
                ConfirmModal(
                    "Cancel Slot",
                    f"Slot {slot_id} has been running for {elapsed:.0f}s.\nCancelling will lose the current progress.",
                    confirm_label="Cancel Slot",
                ),
                _on_confirm,
            )
        else:
            self._do_cancel_slot(slot_id)

    def _do_cancel_slot(self, slot_id: int) -> None:
        """U7: internal cancel — bump generation, cancel worker, update UI."""
        worker = self._slot_workers.get(slot_id)
        if worker is None:
            return
        # U1: show CANCELLING intermediate status while browser process stops
        self._update_slot_status(slot_id, self._format_status("CANCELLING", "badge"))
        self._set_slot_tab_title(slot_id, f"Slot {slot_id} {self._format_status('CANCELLING', 'badge')}")
        self._update_table_row(
            slot_id,
            self._format_status("CANCELLING", "table"),
            self._slot_stats[slot_id].get("file", "-"),
            "stopping…",
        )
        self._slot_generation[slot_id] = self._slot_generation.get(slot_id, 0) + 1
        # AR-2/FE-1: cancel only this slot's run via its own cancel event.
        # Sibling slots' browser contexts are untouched.
        slot_event = self._slot_cancel_events.get(slot_id)
        if slot_event is not None:
            with contextlib.suppress(Exception):
                self._attachment.request_cancel(slot_event)
                self._file_only.request_cancel(slot_event)
        worker.cancel()
        self._slot_workers[slot_id] = None
        # Issue #331: release the per-slot cancel event entry. The cancelled
        # worker holds its own reference to the same Event object; leaving
        # the dict entry behind would leak one Event per cancelled run and
        # could be mistaken for a live, cancellable run.
        self._slot_cancel_events.pop(slot_id, None)
        self._log_msg("[bold {}]CANCELLED:[/] Slot {} stopped by user.".format(THEME["warn"], slot_id), slot_id)
        self._update_slot_status(slot_id, self._format_status("CANCELLED", "badge"))
        self._set_slot_tab_title(slot_id, f"Slot {slot_id} ●")
        self._slot_stats[slot_id]["status"] = "CANCELLED"
        file_name = self._slot_stats[slot_id]["file"]
        self._update_table_row(slot_id, self._format_status("CANCELLED", "table"), file_name, "stopped")
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    def _finalize_slot(
        self,
        slot_id: int,
        status: str,
        filename: str,
        duration: float,
        ok: bool,
        generation: int = 0,
    ) -> None:
        """U7: UI-thread-only finalizer with generation guard.
        If the slot has been restarted or cancelled since this worker began,
        the generation will not match and the stale result is discarded.
        """
        if generation != self._slot_generation.get(slot_id, 0):
            return  # stale worker — slot was cancelled or restarted
        icon = "✓" if ok else "✕"
        self._slot_workers[slot_id] = None
        # AR-2/FE-1: release the per-slot cancel event now the run is done.
        self._slot_cancel_events.pop(slot_id, None)
        self._slot_stats[slot_id] = {"status": status, "file": filename, "duration": duration}
        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(filename)} {icon}")
        self._update_slot_status(slot_id, self._format_status(status, "badge"))
        self._update_table_row(slot_id, self._format_status(status, "table"), filename, f"{duration}s")
        with contextlib.suppress(NoMatches):
            self.query_one(f"#btn-retry-{slot_id}").display = status == "FAILED"
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    def _tick_elapsed(self, slot_id: int) -> None:
        """U4: update the Duration column with live elapsed time."""
        stats = self._slot_stats.get(slot_id)
        if stats is None or stats.get("status") != "RUNNING":
            return
        elapsed = time.perf_counter() - stats.get("_start_perf", time.perf_counter())
        label = f"{elapsed:.0f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        event = stats.get("event")
        status_text = self._format_event_status(event, "table") if event else self._format_status("RUNNING", "table")
        self._update_table_row(
            slot_id,
            status_text,
            stats.get("file", "-"),
            label,
        )

    def _update_slot_event_status(self, slot_id: int, event_name: str) -> None:
        """Render the current pipeline event on the slot badge and table.

        Called from the worker thread via ``call_from_thread``; only updates
        the UI while the slot is still RUNNING so a stale event cannot
        overwrite the terminal SUCCESS/FAILED/CANCELLED state.
        """
        stats = self._slot_stats.get(slot_id)
        if stats is None or stats.get("status") != "RUNNING":
            return
        elapsed = time.perf_counter() - stats.get("_start_perf", time.perf_counter())
        dur_label = f"{elapsed:.0f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        self._update_slot_status(slot_id, self._format_event_status(event_name, "badge"))
        self._update_table_row(
            slot_id,
            self._format_event_status(event_name, "table"),
            stats.get("file", "-"),
            dur_label,
        )

    # ── Adaptive Swarm run / cancel ──────────────────────────────────────

    def _run_swarm(self) -> None:
        if self._swarm is None:
            self.notify("Swarm is not available in this container.", severity="error")
            return
        if self._swarm_id is not None:
            self.notify("A Swarm is already running.", severity="warning")
            return
        try:
            raw_input = self.query_one("#input-swarm-file", Input).value.strip()
            input_path = Path(raw_input).expanduser()
        except Exception as exc:
            self.notify(f"Could not read Swarm input: {exc}", severity="error")
            return
        if not raw_input:
            self.notify("Select a file or folder before starting Swarm.", severity="error")
            return
        # Issue #277: a Swarm that launches 4+ browsers confirms first; below
        # that threshold the start is silent. Presentation lives in the app
        # class so this file stays within its control-flow budget (AES406).
        self._swarm_pending_input = input_path
        self._confirm_or_start_swarm(input_path)

    def _cancel_swarm(self) -> None:
        if self._swarm_id is None or self._swarm is None:
            self.notify("No Swarm is currently running.", severity="warning")
            return
        self._swarm.cancel(self._swarm_id)
        snapshot = self._swarm.snapshot(self._swarm_id)
        if snapshot is not None:
            self._render_swarm_snapshot(snapshot)
        self._log_msg("[bold {}]SWARM:[/] cancelled; active browsers are stopping.".format(THEME["warn"]))

    @work(thread=True)
    def _swarm_worker(self, input_path: Path) -> None:
        try:
            snapshot = self._swarm.start(input_path)
            self._swarm_id = snapshot.swarm_id
            self.call_from_thread(self._render_swarm_snapshot, snapshot)
            self.call_from_thread(
                self._log_msg,
                "[bold {}]SWARM:[/] started {} with {} agents.".format(
                    THEME["accent_fg"], snapshot.swarm_id, len(snapshot.agents)
                ),
            )
            while True:
                time.sleep(1.0)
                latest = self._swarm.snapshot(snapshot.swarm_id)
                if latest is None:
                    break
                self.call_from_thread(self._render_swarm_snapshot, latest)
                if latest.status in {"completed", "partial", "failed", "cancelled"}:
                    self.call_from_thread(
                        self._log_msg,
                        "[bold {}]SWARM:[/] {} ({}/{} completed).".format(
                            THEME["ok"] if latest.status == "completed" else THEME["warn"],
                            latest.status,
                            latest.completed_count,
                            len(latest.agents),
                        ),
                    )
                    break
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]SWARM ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )
        finally:
            self._swarm_id = None

    @work(thread=True)
    def _execute_slot_worker(self, slot_id: int, cfg: AppConfig) -> None:
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        # AR-2/FE-1: pass the per-slot cancel event so the orchestrator can
        # be targeted from _do_cancel_slot without touching sibling slots.
        slot_cancel_event = self._slot_cancel_events.get(slot_id)
        prompt_name = cfg.prompt_path.name if cfg.prompt_path else cfg.input_path.name
        self.call_from_thread(
            self._log_msg,
            "[bold {}]>>> [Slot {}] Starting browser for: {}[/]".format(
                THEME["accent_fg"], slot_id, escape(prompt_name)
            ),
            slot_id,
        )
        start_t = time.perf_counter()
        # U7: capture the generation at worker start for finalize guard
        gen = self._slot_generation.get(slot_id, 0)
        # U4: start periodic elapsed-time updater via call_from_thread
        # (set_timer must be called from the main event loop thread)
        timer_holder: list[Any] = []

        def _create_timer() -> None:
            timer_holder.append(self.set_interval(5.0, lambda: self._tick_elapsed(slot_id)))

        self.call_from_thread(_create_timer)

        def _on_event(_event_type: Any, _event: Any) -> None:
            # Event-level status: render the actual pipeline event (thinking /
            # streaming / prompting) in the slot badge and overview table so a
            # running slot is never just "RUNNING".
            event_name = str(_event.name)
            self._slot_stats.setdefault(slot_id, {})["event"] = event_name
            self.call_from_thread(self._update_slot_event_status, slot_id, event_name)

        try:
            if cfg.file_path:
                res = self._attachment.process_prompt_with_attachment(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    attachment_file=cfg.file_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                    cancel_event=slot_cancel_event,
                    event_observer=_on_event,
                )
            else:
                res = self._file_only.process_prompt_file_only(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                    cancel_event=slot_cancel_event,
                    event_observer=_on_event,
                )
            dur = round(time.perf_counter() - start_t, 1)
            res_str = str(res)
            is_dict_err = isinstance(cast(Any, res), dict) and cast(dict[str, Any], res).get("status") in {
                "error",
                "failure",
                "failed",
            }
            fail_reason = detect_processing_failure(res_str)
            if is_dict_err or fail_reason:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(res_str)),
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False, gen)
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}][Slot {}] SUCCESS:[/] {}".format(THEME["ok"], slot_id, escape(res_str)),
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", prompt_name, dur, True, gen)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(str(exc))),
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False, gen)
        finally:
            if timer_holder:
                self.call_from_thread(timer_holder[0].stop)

    # ── Login worker ─────────────────────────────────────────────────────

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        # U5: update session badge to show login in progress
        with contextlib.suppress(*_BADGE_UNAVAILABLE):
            badge = self.query_one("#session-badge", Label)
            badge.update("SESSION: LOGGING IN…")
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.setup_session()
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN RESULT:[/] {}".format(THEME["ok"], escape(str(res))),
            )
            self.call_from_thread(self._refresh_session_badge)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]LOGIN FAILED:[/] {}".format(THEME["err"], escape(str(exc))),
            )
        finally:
            self._login_in_flight = False

    # ── Session badge ────────────────────────────────────────────────────

    def _refresh_session_badge(self) -> None:
        with contextlib.suppress(*_BADGE_UNAVAILABLE):
            badge = self.query_one("#session-badge", Label)
            if getattr(self, "_session", None) is None:
                badge.update("SESSION: N/A")
            else:
                badge.update("SESSION: CHECKING…")
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
        with contextlib.suppress(*_BADGE_UNAVAILABLE):
            badge = self.query_one("#session-badge", Label)
            # Only show TIMEOUT if the badge is still in CHECKING state.
            if "CHECKING" not in str(badge.render() or ""):
                return
            badge.update("⚠ SESSION: TIMEOUT")
            badge.set_classes("invalid")
        self._log_msg("[bold {}]WARNING:[/] {}".format(THEME["warn"], msg))
        with contextlib.suppress(Exception):
            self.notify(msg, severity="warning", title="Session")

    @work(thread=True)
    def _session_check_worker(self) -> None:
        if self._session is None:
            self.call_from_thread(self._apply_session_badge, False)
            return
        try:
            valid, _msg = self._session.validate_session()
        except Exception:
            valid = False
        self.call_from_thread(self._apply_session_badge, valid)

    def _apply_session_badge(self, valid: bool) -> None:
        self._last_session_state = "VALID" if valid else "EXPIRED"
        with contextlib.suppress(*_BADGE_UNAVAILABLE):
            badge = self.query_one("#session-badge", Label)
            badge.update("SESSION: VALID" if valid else "SESSION: EXPIRED")
            badge.set_classes("invalid" if not valid else "")
        # BUG FIX: cancel the timeout timer when the worker completes.
        # Without this, a 15s timer can fire AFTER the badge is already
        # set to VALID, overwriting it with "TIMEOUT".
        if hasattr(self, "_session_check_timer") and self._session_check_timer is not None:
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
                with contextlib.suppress(NoMatches):
                    self.query_one("#session-total", Label).update(f"TOTAL: {total}")
                    self.query_one("#session-healthy", Label).update(f"HEALTHY: {healthy}")
                    self.query_one("#session-limited", Label).update(f"LIMITED: {limited}")
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
            from modules.core.src.capabilities_session_health_checker import SessionHealthChecker

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

    def _session_login_action(self) -> None:
        """Trigger session login flow."""
        if getattr(self, "_session_manager", None) is None:
            self._log_msg("[yellow]Session manager not available.[/]")
            return
        self._log_msg("[bold {}]>>> Opening session login dialog...[/]".format(THEME["accent_fg"]))
        # For now, log that login would be triggered; the actual flow uses subprocess
        self.notify(
            "Use 'qwen-web-arwaky sessions login --name <name>' command",
            title="Session Login",
            severity="information",
        )


__all__ = ["_TuiWorkersMixin"]
