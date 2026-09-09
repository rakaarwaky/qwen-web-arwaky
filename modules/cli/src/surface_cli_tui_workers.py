"""Background workers and slot execution logic for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing all ``@work(thread=True)``
workers, slot run/cancel/finalise cycle, session badge refresh, and login.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any, cast

from rich.markup import escape
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Input, Label, LoadingIndicator, Switch

from modules.cli.src.surface_cli_tui_css import THEME
from modules.core.src.capabilities_tui_slot_config import SlotInputError
from modules.shared.src.taxonomy_core_vo import AppConfig, HeadlessFlag
from modules.shared.src.utility_core_response import detect_processing_failure


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
    _session_check_timed_out: bool
    _login_in_flight: bool

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    query_one: Any
    notify: Any
    _set_slot_tab_title: Any
    _truncate_name: Any
    _update_slot_status: Any
    _update_table_row: Any
    _refresh_metrics: Any
    call_from_thread: Any
    set_timer: Any
    _ensure_log_handler: Any

    # ── Slot run / cancel ────────────────────────────────────────────────

    def _run_slot(self, slot_id: int) -> None:
        if self._slot_workers.get(slot_id) is not None:
            self._log_msg(f"[bold {THEME['warn']}]WARNING:[/] Slot {slot_id} already running.", slot_id)
            return

        try:
            prompt_val = self.query_one(f"#input-prompt-{slot_id}", Input).value
            file_val = self.query_one(f"#input-file-{slot_id}", Input).value
            out_val = self.query_one(f"#input-output-{slot_id}", Input).value
            headless_val = self.query_one(f"#switch-headless-{slot_id}", Switch).value
        except Exception:
            return

        plan = self._slot_config.resolve_slot_run_plan(prompt_val, file_val, out_val, headless_val)
        if isinstance(plan, SlotInputError):
            msg = f"[bold {THEME['err']}]ERROR:[/] {escape(str(plan.message))} (Slot {slot_id})"
            self._log_msg(msg, slot_id)
            self._log_msg(msg)
            with contextlib.suppress(Exception):
                self.notify(str(plan.message), severity="error", title=f"Slot {slot_id}")
            return

        cfg: AppConfig = plan.config
        p_name = plan.prompt_path.name

        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(p_name)} ⏳")
        self._update_slot_status(slot_id, "STATUS: RUNNING")
        self._slot_stats[slot_id] = {"status": "RUNNING", "file": p_name, "duration": 0.0}
        self._update_table_row(slot_id, "RUNNING ⏳", p_name, "running...")
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_slot_worker(slot_id, cfg)

    def _cancel_slot(self, slot_id: int) -> None:
        worker = self._slot_workers.get(slot_id)
        if worker is None:
            self._log_msg(f"[{THEME['muted']}]No run active in Slot {slot_id}.[/]", slot_id)
            return
        worker.cancel()
        self._slot_workers[slot_id] = None
        self._log_msg(f"[bold {THEME['warn']}]CANCELLED:[/] Slot {slot_id} stopped by user.", slot_id)
        self._update_slot_status(slot_id, "STATUS: CANCELLED")
        self._set_slot_tab_title(slot_id, f"Slot {slot_id} 💤")
        self._slot_stats[slot_id]["status"] = "CANCELLED"
        self._update_table_row(slot_id, "CANCELLED ✕", self._slot_stats[slot_id]["file"], "stopped")
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    def _finalize_slot(self, slot_id: int, status: str, filename: str, duration: float, ok: bool) -> None:
        """C2: UI-thread-only finalizer — mutate slot state atomically.

        Called via ``call_from_thread`` so ``_slot_stats`` / ``_slot_workers``
        are never written from a background thread.
        """
        icon = "✅" if ok else "❌"
        self._slot_workers[slot_id] = None
        self._slot_stats[slot_id] = {"status": status, "file": filename, "duration": duration}
        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {self._truncate_name(filename)} {icon}")
        self._update_slot_status(slot_id, f"STATUS: {status}")
        self._update_table_row(slot_id, f"{'DONE' if ok else 'FAILED'} {icon}", filename, f"{duration}s")
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = False

    @work(thread=True)
    def _execute_slot_worker(self, slot_id: int, cfg: AppConfig) -> None:
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        prompt_name = cfg.prompt_path.name if cfg.prompt_path else cfg.input_path.name
        self.call_from_thread(
            self._log_msg,
            f"[bold {THEME['accent']}]>>> [Slot {slot_id}] Starting browser for: {escape(prompt_name)}[/]",
            slot_id,
        )
        start_t = time.perf_counter()
        try:
            if cfg.file_path:
                res = self._attachment.process_prompt_with_attachment(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    attachment_file=cfg.file_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                )
            else:
                res = self._file_only.process_prompt_file_only(
                    prompt_file=cfg.prompt_path or cfg.input_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
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
                    f"[bold {THEME['err']}][Slot {slot_id}] FAILED:[/] {escape(res_str)}",
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False)
            else:
                self.call_from_thread(
                    self._log_msg,
                    f"[bold {THEME['ok']}][Slot {slot_id}] SUCCESS:[/] {escape(res_str)}",
                    slot_id,
                )
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", prompt_name, dur, True)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                f"[bold {THEME['err']}][Slot {slot_id}] FAILED:[/] {escape(str(exc))}",
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", prompt_name, dur, False)

    # ── Login worker ─────────────────────────────────────────────────────

    @work(thread=True)
    def _login_worker(self) -> None:
        self._ensure_log_handler()
        try:
            if self._setup is None:
                raise RuntimeError("Session setup orchestrator not available.")
            res = self._setup.setup_session()
            self.call_from_thread(
                self._log_msg,
                f"[bold {THEME['ok']}]LOGIN RESULT:[/] {escape(str(res))}",
            )
            self.call_from_thread(self._refresh_session_badge)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                f"[bold {THEME['err']}]LOGIN FAILED:[/] {escape(str(exc))}",
            )
        finally:
            self._login_in_flight = False

    # ── Session badge ────────────────────────────────────────────────────

    def _refresh_session_badge(self) -> None:
        try:
            badge = self.query_one("#session-badge", Label)
        except (LookupError, AttributeError):
            return
        if self._session is None:
            badge.update("SESSION: N/A")
            return
        badge.update("SESSION: CHECKING...")
        self._session_check_timed_out = False
        self.set_timer(15.0, self._session_check_timeout)
        self._session_check_worker()

    def _session_check_timeout(self) -> None:
        if self._session_check_timed_out:
            return
        self._session_check_timed_out = True
        with contextlib.suppress(NoMatches):
            badge = self.query_one("#session-badge", Label)
            badge.update("SESSION: TIMEOUT — run 'qwen-web-arwaky doctor'")
            badge.set_classes("invalid")

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
        try:
            badge = self.query_one("#session-badge", Label)
        except (LookupError, AttributeError):
            return
        badge.update("SESSION: VALID" if valid else "SESSION: EXPIRED")
        badge.set_classes("invalid" if not valid else "")


__all__ = ["_TuiWorkersMixin"]
