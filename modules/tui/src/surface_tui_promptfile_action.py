"""Prompt-pill file dispatch: composer routing and the slot file worker.

FE-3-01: the Prompt pill stores a prompt-file path per slot; Send routes it
through ``process_prompt_file_only``. Split from
``surface_tui_workers_store.py`` so that file stays under the AES surface
complexity budget (AES406). Imported by
:class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import work
from textual.css.query import NoMatches
from textual.widgets import Label, LoadingIndicator

from modules.shared.src.common.taxonomy_core_vo import HeadlessFlag, TimeoutSec
from modules.shared.src.common.utility_response_normalizer import detect_processing_failure
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest
from modules.tui.src.surface_tui_css_view import THEME


class _TuiPromptFileHandlerMixin:
    """Prompt-pill file dispatch and the slot file worker."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _slot_prompt_files: dict[int, str]
    _slot_attachments: dict[int, str]
    _slot_workers: dict[int, Any]
    _slot_cancel_events: dict[int, threading.Event]
    _slot_generation: dict[int, int]
    _slot_stats: dict[int, dict[str, Any]]
    _headless: bool
    _prompt: Any

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Callable[..., None]
    query_one: Callable[..., Any]
    notify: Callable[..., None]
    call_from_thread: Callable[..., Any]
    _truncate_name: Callable[..., str]
    _set_slot_tab_title: Callable[..., None]
    _update_slot_status: Callable[..., None]
    _format_status: Callable[..., str]
    _refresh_metrics: Callable[[], None]
    _ensure_log_handler: Callable[[], None]
    _observe_slot_event: Callable[..., Any]
    _finalize_slot: Callable[..., None]
    _session_resolver: Callable[[], Any]

    def _write_prompt_temp_file(self, slot_id: int, text: str) -> Path | None:
        """Write a composer task to a temporary prompt file (issue #341).

        Lives here only because ``surface_tui_workers_store.py`` is at the
        AES406 control-flow budget. Provenance: the Attach-pill pipeline
        (issue #341) needs a prompt file on disk; this is not FE-3-01 logic.
        Returns None and notifies when the write fails, so the caller can
        abort the run.
        """
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix=f"qwen_slot_{slot_id}_"))
            prompt_path = tmp_dir / "prompt.md"
            prompt_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            msg = f"Cannot write prompt file for Slot {slot_id}: {exc}"
            self._log_msg("[bold {}]ERROR:[/] {}".format(THEME["err"], escape(msg)), slot_id)
            with contextlib.suppress(Exception):
                self.notify(msg, severity="error", title=f"Slot {slot_id}")
            return None
        return prompt_path

    def _dispatch_prompt_file_composer_slot(self, slot_id: int, text: str, prompt_file: str) -> None:
        """FE-3-01: route a Prompt-pill pick through the file pipeline.

        Design decision — refuse (not merge) when the composer also holds a
        typed task or an Attach-pill pick: an ambiguous dispatch on a chat
        console is worse than a clear error. The operator clears one of the
        conflicting inputs (the composer text is the only reachable
        remediation named in the dual-input message; the pick is cleared by
        a vanished path or by picking again).
        """
        if not Path(prompt_file).exists():
            # R2-8: inlined drop — the vanished pick is cleared and the error
            # surfaced at its only call site.
            self._slot_prompt_files.pop(slot_id, None)
            with contextlib.suppress(NoMatches):
                indicator = self.query_one(f"#prompt-file-indicator-{slot_id}", Label)
                indicator.update("")
                indicator.display = False
            self._composer_slot_error(slot_id, f"Picked prompt file no longer exists: {escape(str(prompt_file))}")
            return
        attachment = self._slot_attachments.get(slot_id, "")
        if attachment:
            self._composer_slot_error(
                slot_id,
                "Clear the Attach-pill pick or the Prompt-pill file — not both.",
                severity="warning",
            )
            return
        if text.strip():
            self._composer_slot_error(
                slot_id,
                "Clear the composer text, then Send again.",
                severity="warning",
            )
            return
        if self._prompt is None:
            self._composer_slot_error(slot_id, f"Prompt file capability is not available for Slot {slot_id}.")
            return

        headless = bool(self._headless)
        filename = self._truncate_name(Path(prompt_file).name, 24)
        self._slot_cancel_events[slot_id] = threading.Event()
        self._set_slot_tab_title(slot_id, f"Slot {slot_id}: {filename} ▶")
        with contextlib.suppress(NoMatches):
            self.query_one(f"#btn-retry-{slot_id}").display = False
        self._update_slot_status(slot_id, self._format_status("RUNNING", "badge"))
        self._slot_stats[slot_id] = {
            "status": "RUNNING",
            "file": Path(prompt_file).name,
            "duration": 0.0,
            "event": "EVENT_WEB_LOADED",
            "_start_perf": time.perf_counter(),
        }
        self._refresh_metrics()
        with contextlib.suppress(NoMatches):
            self.query_one(f"#loading-{slot_id}", LoadingIndicator).display = True

        self._slot_workers[slot_id] = self._execute_prompt_file_worker(slot_id, prompt_file, headless)

    def _composer_slot_error(self, slot_id: int, msg: str, *, severity: str = "error") -> None:
        # R2-6: one event, one severity — the slot log and the notification
        # must not mix ERROR and WARNING vocabulary for the same refusal.
        label = "WARNING" if severity == "warning" else "ERROR"
        color = THEME["warn"] if severity == "warning" else THEME["err"]
        self._log_msg(f"[bold {color}]{label}:[/] {msg} (Slot {slot_id})", slot_id)
        with contextlib.suppress(Exception):
            self.notify(msg, severity=severity, title=f"Slot {slot_id}")

    @work(thread=True)
    def _execute_prompt_file_worker(
        self,
        slot_id: int,
        prompt_file: str,
        headless: bool,
    ) -> None:
        """FE-3-01: run one Prompt-pill file through the file pipeline.

        Mirrors ``_execute_direct_worker``: the worker thread takes the
        slot's name so the log handler routes its records into that slot's
        log, and every UI write crosses threads through ``call_from_thread``
        behind the same generation guard the other workers use.
        """
        threading.current_thread().name = f"qwen_slot_worker_{slot_id}"
        self._ensure_log_handler()
        filename = self._truncate_name(Path(prompt_file).name, 24)
        start_t = time.perf_counter()
        gen = self._slot_generation.get(slot_id, 0)
        _on_event = self._observe_slot_event(slot_id)
        prompt_path = Path(prompt_file)

        self.call_from_thread(
            self._log_msg,
            "[bold {}]>>> [Slot {}] Prompt file: {}[/]".format(THEME["accent_fg"], slot_id, escape(filename)),
            slot_id,
        )

        try:
            res = self._prompt.execute(
                PromptRequest(
                    verb="process_prompt_file_only",
                    prompt_file=prompt_path,
                    timeout_sec=TimeoutSec(600),
                    output_file=None,
                    headless=HeadlessFlag(headless),
                    cancel_event=self._slot_cancel_events.get(slot_id),
                    event_observer=_on_event,
                    session_resolver=self._session_resolver(),
                )
            ).response_text
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
                self.call_from_thread(self._finalize_slot, slot_id, "SUCCESS", filename, dur, True, gen)
        except Exception as exc:
            dur = round(time.perf_counter() - start_t, 1)
            self.call_from_thread(
                self._log_msg,
                "[bold {}][Slot {}] FAILED:[/] {}".format(THEME["err"], slot_id, escape(str(exc))),
                slot_id,
            )
            self.call_from_thread(self._finalize_slot, slot_id, "FAILED", filename, dur, False, gen)


__all__ = ["_TuiPromptFileHandlerMixin"]
