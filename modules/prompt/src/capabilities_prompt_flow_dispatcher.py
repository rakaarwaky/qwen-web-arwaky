"""Capabilities: prompt flow dispatcher (AES403).

Implements IPromptFlowProtocol: the shared inject → send → wait-for-response
flow driven by the direct, file-only, and attachment prompt adapters.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page

from modules.shared.src.common.taxonomy_core_constant import MAX_ATTEMPTS, RETRY_BASE_DELAY_SEC
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.common.taxonomy_core_error import (
    RateLimitError,
    ResponseDetectionTimeoutError,
    RunCancelledError,
    StuckDetectedError,
)
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_PROMPT_INJECTED,
    QwenEventType,
)
from modules.shared.src.common.taxonomy_core_vo import (
    AppConfig,
    CancelToken,
    EventSequenceVO,
    HeadlessFlag,
    MessageCount,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    SenderConfig,
    TimeoutSec,
)
from modules.shared.src.common.utility_dom_query import latest_message_text, partial_text_after_stream_cut
from modules.shared.src.common.utility_error_mapping import to_error_response
from modules.shared.src.common.utility_io_writer import save_orchestrator_output
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.prompt.contract_prompt_protocol import (
    IInjectionProtocol,
    IPromptFlowProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.prompt.taxonomy_prompt_vo import ExtractionVerdict, PromptResponse, StreamVerdict


class PromptFlowDispatcher(IPromptFlowProtocol):
    """Drives the shared prompt dispatch and response-wait flow."""

    # ─── Block 2: Protocol Method Implementation ───────────────────────────

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
        cancel_event: CancelToken | None = None,
    ) -> StreamVerdict:
        """Inject prompt, click send, and wait for the AI response.

        ``cancel_event`` is an optional per-run ``threading.Event``.  When it
        is set (by ``request_cancel`` on the owning orchestrator) the flow
        raises ``RunCancelledError`` immediately so the caller's browser
        context is closed without touching sibling runs.

        The returned :class:`StreamVerdict` carries the monitor's extraction
        verdict so a caller can tell a complete response from one the stall
        detector cut. ``StuckDetectedError`` is not retried here: a stalled
        stream is terminal for this run (FRD PROMPT-01, "reports `stalled`
        and does not retry the send") until ``CONFIG-02`` supplies a retry
        budget.
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
                    "Dispatch attempt %d/%d failed (%s: %s); retrying in %ds",
                    attempt,
                    MAX_ATTEMPTS,
                    type(e).__name__,
                    str(e)[:120],
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
                if cancel_event is not None:
                    _interruptible_sleep(cancel_event, delay)
                else:
                    time.sleep(delay)
                continue
            # ``_dispatch_once`` is annotated to return a StreamVerdict and
            # the only production streamer is StreamMonitor, which does; the
            # type checker owns this seam (no runtime assert, no fabricated
            # "complete" for a shape that cannot occur).
            return response
        if cancel_event is not None and cancel_event.is_set():
            raise RunCancelledError("Cancelled by user while waiting for response") from last_error
        raise last_error

    # ─── Block 3: Dunder Methods, Factories, Helpers ───────────────────────

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
        if QwenEventType.DOCUMENT_PARSED in sequence:
            boundary = QwenEventType.DOCUMENT_PARSED
            try:
                return sequence.index(boundary) + 1
            except ValueError:
                return 0
        boundary = QwenEventType.PROMPT_INJECTED
        try:
            return sequence.index(boundary)
        except ValueError:
            return 0

    def _dispatch_once(
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
        sender_config: SenderConfig | None,
        document_parsed: bool,
        cancel_event: CancelToken | None,
    ) -> StreamVerdict:
        """Single inject → send → wait cycle. Raises on failure; caller retries."""
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

        # timeout_sec is a hard response cutoff (issue #372), enforced by the
        # stream monitor; a budget overrun surfaces as
        # ResponseDetectionTimeoutError and this loop retries per MAX_ATTEMPTS.
        try:
            # The protocol annotates this as StreamVerdict (issue #18): the
            # monitor either returns one or raises, so the verdict below is
            # read directly — no legacy str wrap, no None/instance asserts.
            verdict = streamer.wait_for_response(
                page,
                TimeoutSec(timeout_sec),
                msg_count_before,
                emitter,
                polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
                dispatch_acknowledged=HeadlessFlag(state.dispatch_acknowledged),
                baseline_text=baseline_response,
                cancel_event=cancel_event,
            )
        except Exception as err:
            if cancel_event is not None and cancel_event.is_set():
                raise RunCancelledError("Cancelled by user while waiting for response") from err
            raise

        if verdict.text and len(verdict.text.strip()) > 0:
            logger.info("Received response (%d chars)", len(verdict.text))
            return StreamVerdict(text=ResponseText(verdict.text.strip()), verdict=verdict.verdict)

        raise ResponseDetectionTimeoutError("No terminal response event detected before the browser flow ended")

    def mid_stream_cut_outcome(
        self,
        exc: BaseException,
        page: Page,
        *,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        out_path: Path,
        prompt_path: Path,
        elapsed: float,
        ctx: RunContext,
        emitter: LifecycleEmitter | None,
    ) -> PromptResponse:
        """Persist the partial artifact and answer with the honest cut verdict.

        Shared by the file, attachment, and direct pipelines via
        ``IPromptFlowProtocol`` (BE-1-003 / FRD "A response file survives a
        mid-stream extraction failure"): a stall or a hard cut still saves
        whatever the monitor last saw, so the artifact is inspectable, and
        reports ``stalled`` for the stall detector or ``incomplete`` for any
        other non-terminal end (the timeout family).
        ``extraction_verdict=None`` stays reserved for runs where extraction
        never happened (cancel, auth, pre-flight), so callers keep one honest
        field across success and failure paths.
        """
        cut_verdict: ExtractionVerdict = "stalled" if isinstance(exc, StuckDetectedError) else "incomplete"
        failure_reason = to_error_response(exc)
        partial = partial_text_after_stream_cut(exc, page)
        if partial:
            try:
                save_orchestrator_output(saver, out_path, prompt_path, partial, elapsed, ctx, emitter=emitter)
            except Exception as save_exc:
                # The stream failure stays the reported result; a failed partial
                # write must not erase the verdict the caller was promised.
                observability.get_logger().warning(
                    "Partial response artifact could not be saved for %s: %s",
                    out_path,
                    save_exc,
                )
                response = PromptResponse(
                    response_text=ResponseText(
                        f"{failure_reason} (partial response could not be written to {out_path})"
                    ),
                    extraction_verdict=cut_verdict,
                )
            else:
                response = PromptResponse(
                    response_text=ResponseText(f"{failure_reason} (partial saved to {out_path})"),
                    extraction_verdict=cut_verdict,
                )
        else:
            response = PromptResponse(
                response_text=ResponseText(f"{failure_reason} (no partial response available to save)"),
                extraction_verdict=cut_verdict,
            )
        return response


def _interruptible_sleep(cancel_event: CancelToken, seconds: int) -> None:
    """Sleep for ``seconds`` but wake early if ``cancel_event`` is set."""
    cancel_event.wait(timeout=seconds)
