"""Agent: direct text prompt orchestrator (AES405).

Orchestrates direct string text prompt execution without prompt file on disk.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from modules.shared.src.browser.contract_browser_protocol import IBrowserProtocol
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_SESSION_EXPIRED,
    STANDARD_PROMPT_EVENTS,
)
from modules.shared.src.common.taxonomy_core_vo import (
    AppConfig,
    HeadlessFlag,
    JobName,
    OutputPath,
    PromptText,
    ResponseText,
    RunContext,
    RunId,
    TimeoutSec,
)
from modules.shared.src.common.utility_dom_helper import setup_lifecycle_state
from modules.shared.src.common.utility_error_mapping import to_error_response
from modules.shared.src.common.utility_io_writer import save_orchestrator_output
from modules.shared.src.config.utility_config_app_factory import build_app_config, resolve_pipeline_output_path
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.prompt.contract_prompt_protocol import (
    IDirectPromptProtocol,
    IInjectionProtocol,
    IPromptFlowProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    LifecycleObserver,
)
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse

# Block 1: Class Definition & Constructor


class DirectPromptAdapter(IDirectPromptProtocol):
    """Orchestrates direct string text prompt execution."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        flow: IPromptFlowProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._saver = saver
        self._observability = observability
        self._flow = flow

    # Block 2: Protocol Method Implementation

    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        event_observer: LifecycleObserver | None = None,
        session_resolver: Callable[[], Path | None] | None = None,
    ) -> ResponseText:
        """Pipeline 1: Process a direct text prompt string and return AI response.

        ``event_observer`` optionally receives every emitted lifecycle event
        so a surface can render event-level status (thinking / streaming /
        prompting) instead of only IDLE/RUNNING.

        ``session_resolver`` returns the session pool path chosen by session
        rotation upstream of this pipeline. The pipeline builds its own
        AppConfig, so without the resolver the pool choice would be dropped
        and the default session used; a single-session pool must resolve the
        logged-in profile through the resolver as well.
        """
        ctx = RunContext()
        try:
            prompt_str = str(prompt)
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(prompt_str)

                p_path, out_path = resolve_pipeline_output_path(Path(tmp_path), output_file)
                cfg = build_app_config(
                    input_path=p_path,
                    output_path=out_path,
                    headless=headless,
                    session_path=self._resolve_session_path(session_resolver),
                )
                self._observability.bind_run_context(RunId(ctx.run_id), job_name=JobName("direct"))
                self._observability.attach_run_log(job_name=JobName("direct"), run_id=RunId(ctx.run_id))
                emitter, state = setup_lifecycle_state(self._observability.get_logger(), STANDARD_PROMPT_EVENTS)
                if event_observer is not None:
                    emitter.observe(event_observer)
                t0 = time.time()
                with self._browser.browser_session(cfg) as bctx:
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    text = self._execute_direct_on_page(page, p_path, prompt_str, int(timeout_sec), cfg, emitter, state)
                dur = time.time() - t0
                save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx, emitter=emitter)
                return ResponseText(text)
            finally:
                p = Path(tmp_path)
                if p.exists():
                    p.unlink()
        except Exception as exc:
            return to_error_response(exc)
        finally:
            self._observability.detach_run_log(RunId(ctx.run_id))
            self._observability.clear_run_context()

    # Block 3: Dunder Methods, Factories & Helpers

    @staticmethod
    def _resolve_session_path(session_resolver: Callable[[], Path | None] | None) -> Path | None:
        """Run the pool resolver; an empty pool must fall back to the default.

        ``build_app_config`` falls back to ``DEFAULT_SESSION`` when nothing
        is supplied, so a resolver that returned ``None`` reports the
        default session back to the pipeline. A resolver that raises
        reports no session instead of failing the prompt.
        """
        if session_resolver is None:
            return None
        try:
            return session_resolver()
        except Exception:
            return None

    def _execute_direct_on_page(
        self,
        page: Page,
        filepath: Path,
        prompt: str,
        timeout_sec: int,
        active_cfg: AppConfig,
        emitter: LifecycleEmitter,
        state: LifecycleState,
    ) -> str:
        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        try:
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
            )
        except Exception:
            if self._browser.detect_session_expired(page):
                emitter.emit(EVENT_SESSION_EXPIRED, {"url": page.url, "reason": "post_send_banner"})
            raise

    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run one prompt verb and return the answer, with failures carried.

        The verb method on this class reports a failure as an error-text
        response, so the aggregate seam returns that text unchanged; a
        surface renders the problem without a try/except.
        """
        if request.verb == "process_direct_prompt":
            return PromptResponse(
                response_text=self.process_direct_prompt(
                    prompt=request.prompt,
                    timeout_sec=request.timeout_sec,
                    output_file=request.output_file,
                    headless=request.headless,
                    event_observer=request.event_observer,
                    session_resolver=request.session_resolver,
                )
            )
        if request.verb == "request_cancel":
            return PromptResponse(cancelled=True)
        return PromptResponse(response_text=ResponseText(f"ERROR: unknown prompt verb {request.verb!r}"))


__all__ = ["DirectPromptAdapter"]
