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
from textual.widgets import Input, LoadingIndicator, Switch

from modules.cli.src.surface_cli_tui_css import THEME
from modules.shared.src.taxonomy_core_vo import AppConfig, FilePath, HeadlessFlag, PromptText, SlotInputValue
from modules.shared.src.taxonomy_setup_vo import SetupRequest
from modules.shared.src.taxonomy_swarm_vo import SwarmRequest
from modules.shared.src.utility_response_normalizer import detect_processing_failure

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
    _swarm_started_perf: float | None
    _session_check_timed_out: bool
    _last_session_state: str | None
    _login_in_flight: bool
    _slot_generation: dict[int, int]
    _slot_cancel_events: dict[int, threading.Event]
    _direct: Any

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    _append_chat_message: Any
    _render_account_cards: Any
    query_one: Any
    notify: Any
    _set_slot_tab_title: Any
    _truncate_name: Any
    _update_slot_status: Any
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

        # The chat console's transcript mirrors what this slot was asked to
        # do, so a run started from Settings still shows up in the Chat view.
        self._append_chat_message(slot_id, "user", p_name, attachment=file_val)

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
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_slot_worker(slot_id, cfg)

    def _run_composer_slot(self, slot_id: int, text: str) -> None:
        """Dispatch a chat-console task as a direct text prompt.

        The composer is the mockup's inline execution surface: it takes a
        typed task instead of a prompt file, so it runs through the direct
        prompt capability while reusing the same per-slot status, table, and
        finalize plumbing every other run uses.
        """
        if self._slot_workers.get(slot_id) is not None:
            self._log_msg("[bold {}]WARNING:[/] Slot {} already running.".format(THEME["warn"], slot_id), slot_id)
            with contextlib.suppress(Exception):
                self.notify(f"Slot {slot_id} is already running.", severity="warning", title=f"Slot {slot_id}")
            return
        if getattr(self, "_direct", None) is None:
            msg = f"Direct prompt capability is not available for Slot {slot_id}."
            self._log_msg("[bold {}]ERROR:[/] {}".format(THEME["err"], escape(msg)), slot_id)
            with contextlib.suppress(Exception):
                self.notify(msg, severity="error", title=f"Slot {slot_id}")
            return

        headless = True
        out_val = ""
        with contextlib.suppress(Exception):
            headless = self.query_one(f"#switch-headless-{slot_id}", Switch).value
            out_val = self.query_one(f"#input-output-{slot_id}", Input).value

        filename = self._truncate_name(text, 24)
        self._slot_cancel_events[slot_id] = threading.Event()
        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {filename} ▶")
        with contextlib.suppress(NoMatches):
            self.query_one(f"#btn-retry-{slot_id}").display = False
        self._update_slot_status(slot_id, self._format_status("RUNNING", "badge"))
        self._slot_stats[slot_id] = {
            "status": "RUNNING",
            "file": filename,
            "duration": 0.0,
            "event": "EVENT_WEB_LOADED",
            "_start_perf": time.perf_counter(),
        }
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_direct_worker(slot_id, text, headless, out_val)

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
        with contextlib.suppress(NoMatches):
            self.query_one(f"#btn-retry-{slot_id}").display = status == "FAILED"
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    def _update_slot_event_status(self, slot_id: int, event_name: str) -> None:
        """Render the current pipeline event on the slot badge.

        Called from the worker thread via ``call_from_thread``; only updates
        the UI while the slot is still RUNNING so a stale event cannot
        overwrite the terminal SUCCESS/FAILED/CANCELLED state.
        """
        stats = self._slot_stats.get(slot_id)
        if stats is None or stats.get("status") != "RUNNING":
            return
        self._update_slot_status(slot_id, self._format_event_status(event_name, "badge"))

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
        self._swarm.execute(SwarmRequest(verb="cancel", swarm_id=self._swarm_id))
        snapshot = self._swarm.execute(SwarmRequest(verb="snapshot", swarm_id=self._swarm_id)).snapshot
        if snapshot is not None:
            self._render_swarm_snapshot(snapshot)
        self._log_msg("[bold {}]SWARM:[/] cancelled; active browsers are stopping.".format(THEME["warn"]))

    @work(thread=True)
    def _swarm_worker(self, input_path: Path) -> None:
        try:
            snapshot = self._swarm.execute(SwarmRequest(verb="start", input_path=input_path)).snapshot
            assert snapshot is not None
            self._swarm_id = snapshot.swarm_id
            # Overview Swarm Status card shows Uptime Elapsed from this stamp.
            self._swarm_started_perf = time.perf_counter()
            self.call_from_thread(self._render_swarm_snapshot, snapshot)
            self.call_from_thread(
                self._log_msg,
                "[bold {}]SWARM:[/] started {} with {} agents.".format(
                    THEME["accent_fg"], snapshot.swarm_id, len(snapshot.agents)
                ),
            )
            while True:
                time.sleep(1.0)
                latest = self._swarm.execute(SwarmRequest(verb="snapshot", swarm_id=snapshot.swarm_id)).snapshot
                if latest is None:
                    break
                self.call_from_thread(self._render_swarm_snapshot, latest)
                self.call_from_thread(self._refresh_metrics)
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
            self._swarm_started_perf = None
            self.call_from_thread(self._refresh_metrics)

    def _observe_slot_event(self, slot_id: int) -> Any:
        """Build the lifecycle observer that mirrors pipeline events into the UI."""

        def _on_event(_event_type: Any, _event: Any) -> None:
            # Event-level status: render the actual pipeline event (thinking /
            # streaming / prompting) in the slot badge and overview table so a
            # running slot is never just "RUNNING".
            event_name = str(_event.name)
            self._slot_stats.setdefault(slot_id, {})["event"] = event_name
            self.call_from_thread(self._update_slot_event_status, slot_id, event_name)

        return _on_event

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
        _on_event = self._observe_slot_event(slot_id)

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
                self.call_from_thread(self._append_chat_message, slot_id, "agent", res_str)
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", prompt_name, dur, True, gen)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(str(exc))),
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False, gen)

    @work(thread=True)
    def _execute_direct_worker(
        self,
        slot_id: int,
        prompt: str,
        headless: bool,
        output_val: str,
    ) -> None:
        """Run one composer task through the direct prompt capability.

        Mirrors ``_execute_slot_worker``: the worker thread takes the slot's
        name so the log handler routes its records into that slot's event
        log, and every UI write crosses threads through ``call_from_thread``
        behind the same generation guard a file run uses.
        """
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        filename = self._truncate_name(prompt, 24)
        start_t = time.perf_counter()
        gen = self._slot_generation.get(slot_id, 0)
        _on_event = self._observe_slot_event(slot_id)

        self.call_from_thread(
            self._log_msg,
            "[bold {}]>>> [Slot {}] Direct prompt: {}[/]".format(THEME["accent_fg"], slot_id, escape(filename)),
            slot_id,
        )

        try:
            res = self._direct.process_direct_prompt(
                prompt=PromptText(prompt),
                timeout_sec=600,
                output_file=Path(output_val) if output_val.strip() else None,
                headless=HeadlessFlag(headless),
                event_observer=_on_event,
            )
            dur = round(time.perf_counter() - start_t, 1)
            res_str = str(res)
            fail_reason = detect_processing_failure(res_str)
            if fail_reason is not None:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(str(fail_reason))),
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "FAILED", filename, dur, False, gen)
            else:
                self.call_from_thread(
                    self._log_msg,
                    "[bold {}][Slot {}] SUCCESS:[/] {}".format(THEME["ok"], slot_id, escape(res_str)),
                    slot_id,
                )
                self.call_from_thread(self._append_chat_message, slot_id, "agent", res_str)
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", filename, dur, True, gen)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(str(exc))),
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", filename, dur, False, gen)


__all__ = ["_TuiWorkersMixin"]
