"""Agent: attachment prompt orchestrator (AES405).

Orchestrates prompt execution with mandatory document file attachment (.pdf, .md, .txt).
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_dom_helper import setup_lifecycle_state
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IAttachmentPromptAggregate, IPromptFlowAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    IUploadProtocol,
)
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import UploadFailureError
from modules.shared.src.taxonomy_core_event import PIPELINE_EVENT_SEQUENCE
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    HeadlessFlag,
    OutputPath,
    PromptPath,
    ResponseText,
    RunContext,
    SenderConfig,
)


class AttachmentPromptOrchestrator(IAttachmentPromptAggregate):
    """Orchestrates prompt execution with document file attachment."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        uploader: IUploadProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        flow: IPromptFlowAggregate,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._uploader = uploader
        self._saver = saver
        self._observability = observability
        self._flow = flow

    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
    ) -> ResponseText:
        """Pipeline 3: Process a prompt file from disk with document attachment."""
        try:
            p_path = Path(prompt_file).resolve()
            if not p_path.exists():
                raise FileNotFoundError(f"Input file not found: {p_path}")

            att_path = Path(attachment_file).resolve()
            if not att_path.exists():
                raise FileNotFoundError(f"Attachment file not found: {att_path}")

            out_path = Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / p_path.name
            if out_path.is_dir():
                out_path = out_path / f"{p_path.stem}_output.md"

            cfg = build_app_config(
                input_path=p_path,
                file_path=att_path,
                output_path=out_path,
                headless=headless,
            )
            ctx = RunContext()
            emitter, state = setup_lifecycle_state(self._observability.get_logger(), PIPELINE_EVENT_SEQUENCE)

            t0 = time.time()
            with self._browser.browser_session(cfg) as bctx:
                page = bctx.pages[0] if bctx.pages else bctx.new_page()
                text = self._execute_attachment_on_page(
                    page, p_path, att_path, cfg.request_timeout, cfg, emitter, state
                )
            dur = time.time() - t0
            save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx, emitter=emitter)
            return ResponseText(f"Successfully processed {p_path.name} with attachment {att_path.name} -> {out_path}")
        except Exception as exc:
            return to_error_response(exc)

    def _execute_attachment_on_page(
        self,
        page: Page,
        filepath: Path,
        att_path: Path,
        timeout_sec: int,
        active_cfg: AppConfig,
        emitter: LifecycleEmitter,
        state: LifecycleState,
    ) -> str:
        logger = self._observability.get_logger()

        prompt = filepath.read_text(encoding="utf-8").strip()

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)
        attached = self._uploader.upload_attachment(
            page, att_path, emitter=emitter, web_loaded=HeadlessFlag(state.web_loaded)
        )
        if not attached or not state.file_uploaded or not state.document_parsed:
            upload_error = getattr(self._uploader, "last_error", None)
            detail = f": {upload_error}" if upload_error else ""
            logger.error("File upload or parsing could not be positively verified: %s%s", att_path.name, detail)
            raise UploadFailureError(f"Attachment upload/parsing failed for {att_path.name}{detail}")

        # Use a generous timeout so _wait_for_send_enabled can hold for
        # long document parsing (up to 120s) before the first click attempt.
        send_cfg = SenderConfig(
            click_timeout_ms=120_000,
            try_enter_key_fallback=True,
        )
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
            sender_config=send_cfg,
            document_parsed=state.document_parsed,
        )


__all__ = ["AttachmentPromptOrchestrator"]
