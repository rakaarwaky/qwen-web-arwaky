"""Capability layer (capabilities_prompt_flow): shared inject → send → wait.

This is the shared dispatch-and-wait sequence the three prompt adapters
(deprecated as the adapter classes themselves are the aggregate entry
points) call through :class:`PromptFlow` after each adapter has resolved
its own pre-conditions — browser session, output path, cancel registry.

The adapters own the surface verb routing and the per-adapter browser
session lifecycle; they hand a page, filepath, prompt, and pre-built
state to :meth:`dispatch_and_wait_for_response` once those pre-conditions
are met.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from playwright.sync_api import Page

from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_prompt_protocol import (
    IPromptFlowProtocol,
    IPromptInjectorProtocol,
    IPromptSenderProtocol,
    IPromptStreamProtocol,
)
from modules.shared.src.taxonomy_core_constant import MAX_ATTEMPTS, RETRY_BASE_DELAY_SEC
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import (
    RateLimitError,
    ResponseDetectionTimeoutError,
    RunCancelledError,
)
from modules.shared.src.taxonomy_core_event import EVENT_PROMPT_INJECTED, QwenEventType
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    EventSequenceVO,
    MessageCount,
    PollIntervalSec,
    ResponseText,
    SenderConfig,
    TimeoutSec,
)
from modules.shared.src.utility_dom_query import latest_message_text


class PromptFlow(IPromptFlowProtocol):
    """Shared inject → send → wait-for-response flow."""

    @staticmethod
    def _attempt_boundary_index(emitter: LifecycleEmitter) -> int:
        """Index of the last event belonging to the pre-attempt phase.

        The dispatch loop re-emits events from the prompt-injection point
        onward (and, for attachment pipelines, from the document-parse
        point onward when that event is in the configured sequence).
        Events before that boundary — page load, login, model, and file
        upload when the attachment pipeline ran — are never re-emitted on
        retry, so the gate keeps them accepted.

        Returns ``0`` when the gate has no recorded progress (fresh run),
        meaning nothing is re-seeded.
        """
        sequence = emitter.sequence
        if not sequence:
            return 0
        # Find the first event the dispatch loop re-emits: PROMPT_INJECTED
        # for standard pipelines, DOCUMENT_PARSED for attachment pipelines
        # (the uploader emits it once, but the flow guard re-checks it
        # via ``state.document_parsed`` on every attempt).
        if QwenEventType.DOCUMENT_PARSED in sequence:
            # DOCUMENT_PARSED is emitted once by the uploader before the
            # dispatch loop and is NOT re-emitted on retry. Preserve it in the
            # gate by returning index+1 so the slice `completed[:boundary]`
            # includes it.
            boundary = QwenEventType.DOCUMENT_PARSED
            try:
                return sequence.index(boundary) + 1
            except ValueError:
                return 0
        else:
            boundary = QwenEventType.PROMPT_INJECTED
            try:
                return sequence.index(boundary)
            except ValueError:
                return 0

    def dispatch_and_wait_for_response(
        self,
        page: Page,
        filepath: Path,
        prompt: str,
        msg_count_before: MessageCount,
        timeout_sec: TimeoutSec,
        active_cfg: AppConfig,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        observability: IObservabilityProtocol,
        injector: IPromptInjectorProtocol,
        sender: IPromptSenderProtocol,
        streamer: IPromptStreamProtocol,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
        cancel_event: threading.Event | None = None,
    ) -> ResponseText:
        """Inject prompt, click send, and wait for the AI response.

        ``cancel_event`` is an optional per-run ``threading.Event``.  When it
        is set (by ``request_cancel`` on the owning adapter) the flow
        raises ``RunCancelledError`` immediately so the caller's browser
        context is closed without touching sibling runs.
        """
        if cancel_event is not None and cancel_event.is_set():
            raise RunCancelledError("Cancelled by user before dispatch")
        logger = observability.get_logger()

        last_error: Exception
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._dispatch_once(
                    page,
                    injector,
                    sender,
                    streamer,
                    emitter,
                    state,
                    observability,
                    filepath,
                    prompt,
                    msg_count_before,
                    timeout_sec,
                    active_cfg,
                    sender_config,
                    document_parsed,
                    cancel_event,
                )
            except (RateLimitError, ResponseDetectionTimeoutError) as e:
                last_error = e
                if cancel_event is not None and cancel_event.is_set():
                    break
                if attempt >= MAX_ATTEMPTS:
                    raise
                delay = RETRY_BASE_DELAY_SEC * attempt
                logger.warning(
                    "Dispatch attempt %d/%d failed (%s); retrying in %ds",
                    attempt,
                    MAX_ATTEMPTS,
                    type(e).__name__,
                    delay,
                )
                gate = emitter.gate
                if gate is not None:
                    # Roll back only the events this attempt emitted (from
                    # PROMPT_INJECTED onward, or from DOCUMENT_PARSED onward
                    # for attachment pipelines). The page/attachment-phase
                    # prefix stays accepted because it is not re-emitted on
                    # retry: the browser and attachment pipeline run once,
                    # before the dispatch loop.
                    boundary = self._attempt_boundary_index(emitter)
                    gate.reset(completed_prefix=EventSequenceVO(gate.completed[:boundary]))
                time.sleep(delay)
            else:
                return ResponseText(response)

        if cancel_event is not None and cancel_event.is_set():
            raise RunCancelledError("Cancelled by user while waiting for response") from last_error
        raise last_error

    def _dispatch_once(
        self,
        page: Page,
        injector: IPromptInjectorProtocol,
        sender: IPromptSenderProtocol,
        streamer: IPromptStreamProtocol,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        observability: IObservabilityProtocol,
        filepath: Path,
        prompt: str,
        msg_count_before: MessageCount,
        timeout_sec: TimeoutSec,
        active_cfg: AppConfig,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Single inject → send → wait cycle. Raises on failure; caller retries."""
        logger = observability.get_logger()
        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None

        injector.inject_text(page, prompt)
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        if sender_config is not None:
            sender.click_send(page=page, emitter=emitter, config=sender_config, document_parsed=document_parsed)
        else:
            sender.click_send(page=page, emitter=emitter, document_parsed=document_parsed)

        if not state.dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")

        # timeout_sec is a hard response cutoff (issue #372), enforced by the
        # stream monitor; a budget overrun surfaces as
        # ResponseDetectionTimeoutError and this loop retries per MAX_ATTEMPTS.
        try:
            response = streamer.wait_for_response(
                page=page,
                timeout_sec=timeout_sec,
                msg_count_before=msg_count_before,
                emitter=emitter,
                polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
                dispatch_acknowledged=state.dispatch_acknowledged,
                baseline_text=baseline_response,
                cancel_event=cancel_event,
            )
        except Exception as err:
            if cancel_event is not None and cancel_event.is_set():
                raise RunCancelledError("Cancelled by user while waiting for response") from err
            raise

        text = str(response) if response else ""
        if text.strip():
            logger.info("Received response (%d chars)", len(text))
            return text.strip()

        raise ResponseDetectionTimeoutError("No terminal response event detected before the browser flow ended")


__all__ = ["PromptFlow"]
