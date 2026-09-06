"""Agent: shared prompt-flow orchestrator (AES405).

Implements IPromptFlowAggregate: the shared inject → send → wait-for-response
flow used by the direct, file-only, and attachment prompt orchestrators.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_dom_query import latest_message_text
from modules.shared.src.contract_core_aggregate import IPromptFlowAggregate
from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    IObservabilityProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
from modules.shared.src.taxonomy_core_event import EVENT_PROMPT_INJECTED
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    HeadlessFlag,
    MessageCount,
    PollIntervalSec,
    PromptText,
    SenderConfig,
    TimeoutSec,
)


class SharedFlowOrchestrator(IPromptFlowAggregate):
    """Orchestrates the shared prompt dispatch and response-wait flow."""

    def dispatch_and_wait_for_response(
        self,
        page: Page,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        observability: IObservabilityProtocol,
        filepath: Path,
        prompt: str,
        msg_count_before: MessageCount,
        timeout_sec: int,
        active_cfg: AppConfig,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> str:
        """Inject prompt, click send, and wait for the AI response."""
        logger = observability.get_logger()
        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None

        injector.inject_text(page, PromptText(prompt))
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        if sender_config is not None:
            sender.click_send(
                page,
                emitter,
                config=sender_config,
                document_parsed=HeadlessFlag(document_parsed),
            )
        else:
            sender.click_send(page, emitter, document_parsed=HeadlessFlag(document_parsed))

        if not state.dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")

        response_timeout_hint = timeout_sec
        response = streamer.wait_for_response(
            page,
            TimeoutSec(response_timeout_hint),
            msg_count_before,
            emitter,
            polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
            dispatch_acknowledged=HeadlessFlag(state.dispatch_acknowledged),
            baseline_text=baseline_response,
        )

        if response and len(response.strip()) > 0:
            logger.info("Received response (%d chars)", len(response))
            return response.strip()

        raise ResponseDetectionTimeoutError("No terminal response event detected before the browser flow ended")


__all__ = ["SharedFlowOrchestrator"]
