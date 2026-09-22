"""Agent: prompt file orchestrator (AES405).

Orchestrates prompt execution from local prompt file (.md) without attachment.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import (
    build_app_config,
    resolve_pipeline_output_path,
)
from modules.core.src.utility_core_dom_helper import setup_lifecycle_state
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IPromptFileAggregate, IPromptFlowAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    IRunCancelProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import RunCancelledError
from modules.shared.src.taxonomy_core_event import STANDARD_PROMPT_EVENTS
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    HeadlessFlag,
    JobName,
    OutputPath,
    PromptPath,
    ResponseText,
    RunContext,
    RunId,
    RunState,
)


def new_run_state(cancel_event: threading.Event | None = None) -> RunState:
    """Create per-run state, reusing the caller event when supplied."""
    if cancel_event is not None:
        return RunState(cancel_event=cancel_event)
    return RunState()


class PromptFileOrchestrator(IPromptFileAggregate):
    """Orchestrates prompt file execution (without document attachment)."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        flow: IPromptFlowAggregate,
        cancel: IRunCancelProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._saver = saver
        self._observability = observability
        self._flow = flow
        self._cancel = cancel

    def request_cancel(self, cancel_event: threading.Event) -> None:
        """Cancel a specific in-flight run identified by its cancel event.

        The caller (e.g. the TUI slot worker) creates its own
        ``threading.Event`` per run, passes it into
        ``process_prompt_file_only``, and later calls this method with the
        same event to stop *only that run*. Sibling runs holding different
        events are unaffected.
        """
        self._cancel.cancel_run(cancel_event)

    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: threading.Event | None = None,
    ) -> ResponseText:
        """Pipeline 2: Process a prompt file from disk without attachment.

        Pass ``cancel_event`` to enable targeted cancellation: the TUI
        worker creates one ``threading.Event`` per slot and hands it in;
        ``request_cancel`` can then stop only that slot's run without
        closing sibling slots' browser contexts. When omitted (non-TUI
        callers), a private event is used internally and the run is not
        externally cancellable.
        """
        ctx = RunContext()
        run_state = new_run_state(cancel_event)
        self._cancel.register(run_state)
        try:
            p_path, out_path = resolve_pipeline_output_path(prompt_file, output_file)
            cfg = build_app_config(
                input_path=p_path,
                output_path=out_path,
                headless=headless,
            )
            self._observability.bind_run_context(RunId(ctx.run_id), job_name=JobName(p_path.stem))
            self._observability.attach_run_log(job_name=JobName(p_path.stem), run_id=RunId(ctx.run_id))
            emitter, state = setup_lifecycle_state(self._observability.get_logger(), STANDARD_PROMPT_EVENTS)

            t0 = time.time()
            with self._browser.browser_session(cfg) as bctx:
                self._cancel.set_active_bctx(run_state.cancel_event, bctx)
                try:
                    if run_state.cancel_event.is_set():
                        raise RunCancelledError("Cancelled by user before browser launch")
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    text = self._execute_file_on_page(
                        page, p_path, cfg.request_timeout, cfg, emitter, state, run_state.cancel_event
                    )

                finally:
                    self._cancel.set_active_bctx(run_state.cancel_event, None)
            dur = time.time() - t0
            save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx, emitter=emitter)
            return ResponseText(f"Successfully processed {p_path.name} -> {out_path}")
        except Exception as exc:
            return to_error_response(exc)
        finally:
            self._cancel.release(run_state)
            self._observability.detach_run_log(RunId(ctx.run_id))
            self._observability.clear_run_context()

    def _execute_file_on_page(
        self,
        page: Page,
        filepath: Path,
        timeout_sec: int,
        active_cfg: AppConfig,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        cancel_event: threading.Event | None = None,
    ) -> str:
        prompt = filepath.read_text(encoding="utf-8").strip()

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)

        return self._flow.dispatch_and_wait_for_response(
            page=page,
            injector=self._injector,
            sender=self._sender,
            streamer=self._streamer,
            emitter=emitter,
            state=state,
            observability=self._observability,
            filepath=filepath,
            prompt=prompt,
            msg_count_before=msg_count_before,
            timeout_sec=timeout_sec,
            active_cfg=active_cfg,
            cancel_event=cancel_event,
        )


__all__ = ["PromptFileOrchestrator"]
