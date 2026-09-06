"""Agent: direct text prompt orchestrator (AES405).

Orchestrates direct string text prompt execution without prompt file on disk.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config, resolve_pipeline_output_path
from modules.core.src.utility_core_dom_helper import setup_lifecycle_state
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IDirectPromptAggregate, IPromptFlowAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_event import STANDARD_PROMPT_EVENTS
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    HeadlessFlag,
    OutputPath,
    PromptText,
    ResponseText,
    RunContext,
    TimeoutSec,
)


class DirectPromptOrchestrator(IDirectPromptAggregate):
    """Orchestrates direct string text prompt execution."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        flow: IPromptFlowAggregate,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._saver = saver
        self._observability = observability
        self._flow = flow

    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
    ) -> ResponseText:
        """Pipeline 1: Process a direct text prompt string and return AI response."""
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
                )
                ctx = RunContext()
                emitter, state = setup_lifecycle_state(self._observability.get_logger(), STANDARD_PROMPT_EVENTS)
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


__all__ = ["DirectPromptOrchestrator"]
