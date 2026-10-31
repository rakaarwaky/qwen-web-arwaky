"""Agent: prompt runtime orchestrator (AES405).

Implements IPromptRuntimeAggregate: the single aggregate entry point for the
prompt_runtime feature. A surface holds this one object and calls
:meth:`execute` with a ``RuntimeRequest``; the orchestrator routes the
request to the capability seam that serves its verb, so no surface has to
know which of the five runtime capabilities owns which verb.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from playwright.sync_api import Page

from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.common.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    InjectorConfig,
    MessageCount,
    MinTextLength,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    SenderConfig,
    StabilityChecks,
    StreamerConfig,
    TimeoutSec,
)
from modules.shared.src.prompt.contract_prompt_protocol import (
    IInjectionProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    IUploadProtocol,
)
from modules.shared.src.prompt_runtime.contract_prompt_runtime_aggregate import IPromptRuntimeAggregate
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import (
    RuntimeRequest,
    RuntimeResponse,
)


class PromptRuntimeOrchestrator(IPromptRuntimeAggregate):
    """Route a runtime request to the capability that serves its verb.

    The five runtime capabilities each serve one verb of this aggregate —
    ``inject`` → ``IInjectionProtocol.inject_text``, ``send`` →
    ``ISendProtocol.click_send`` (plus ``count_messages`` so the response
    carries the post-dispatch turn count), ``watch`` →
    ``IStreamProtocol.wait_for_response``, ``upload`` →
    ``IUploadProtocol.upload_attachment``, ``persist`` →
    ``ISaverProtocol.write_output``. A surface that called them directly
    would have to branch on the verb itself; holding the branch here keeps
    it in one place: the surface sends a request and gets a response, and
    the orchestrator picks the capability.

    This agent is a routing facade, not a pipeline: it never sequences
    inject → send → wait (that ordering belongs to ``PromptFlowDispatcher``
    behind ``IPromptAggregate`` in ``modules/prompt``), and it imports no
    runtime capability module — only the shared protocol interfaces those
    capabilities implement (AES201: agent imports contracts, never
    capabilities).

    Raises:
        QwenCliError: When a verb is added to ``RuntimeVerb`` without a
            capability being wired for it here, or when a verb is called
            with a required request slot (emitter, filepath, output_path)
            missing.
    """

    def __init__(
        self,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        uploader: IUploadProtocol,
        saver: ISaverProtocol,
    ) -> None:
        """Hold the one capability that serves each runtime verb.

        Args:
            injector: Serves ``inject`` (DOM prompt injection).
            sender: Serves ``send`` (dispatch click + turn count).
            streamer: Serves ``watch`` (response wait and verdict).
            uploader: Serves ``upload`` (pre-flight validation + attach).
            saver: Serves ``persist`` (artifact write + metadata sidecar).
        """
        self._by_verb: dict[str, Callable[[RuntimeRequest], RuntimeResponse]] = {
            "inject": self._inject,
            "send": self._send,
            "watch": self._watch,
            "upload": self._upload,
            "persist": self._persist,
        }
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._uploader = uploader
        self._saver = saver

    # Block 2: Protocol Method Implementation
    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        """Route *request* to the capability that serves its verb.

        Returns:
            RuntimeResponse: The capability's outcome — the artifact path
            for ``persist``, the turn count for ``send``, the text and
            verdict for ``watch``, the upload verdict for ``upload``, and
            the default response for ``inject``.

        Raises:
            QwenCliError: When no capability is wired for
                ``request.verb``, or the verb's required request slot is
                missing.
        """
        route = self._by_verb.get(request.verb)
        if route is None:
            raise QwenCliError(f"No prompt-runtime capability serves verb {request.verb!r}")
        return route(request)

    # Block 3: Dunder Methods, Factories, Helpers
    def _inject(self, request: RuntimeRequest) -> RuntimeResponse:
        """Inject the prompt text into the page's chat input."""
        self._injector.inject_text(
            page=cast(Page, request.page),
            text=PromptText(str(request.prompt)),
            config=cast(InjectorConfig | None, request.config),
        )
        return RuntimeResponse()

    def _send(self, request: RuntimeRequest) -> RuntimeResponse:
        """Dispatch the send action and report the post-dispatch turn count."""
        if request.emitter is None:
            raise QwenCliError("send verb requires request.emitter (the lifecycle emitter the dispatcher writes to)")
        page = cast(Page, request.page)
        emitter = cast(LifecycleEmitter, request.emitter)
        self._sender.click_send(
            page=page,
            emitter=emitter,
            config=cast(SenderConfig | None, request.config),
            document_parsed=HeadlessFlag(bool(request.document_parsed)),
        )
        count: MessageCount = self._sender.count_messages(page)
        return RuntimeResponse(message_count=count)

    def _watch(self, request: RuntimeRequest) -> RuntimeResponse:
        """Wait for a stable assistant response and report text + verdict."""
        if request.emitter is None:
            raise QwenCliError("watch verb requires request.emitter (the lifecycle emitter the monitor writes to)")
        cfg = request.config if isinstance(request.config, StreamerConfig) else StreamerConfig()
        verdict = self._streamer.wait_for_response(
            page=cast(Page, request.page),
            timeout_sec=TimeoutSec(int(request.timeout_sec)),
            msg_count_before=MessageCount(int(request.msg_count_before)),
            emitter=cast(LifecycleEmitter, request.emitter),
            polling_interval_sec=PollIntervalSec(cfg.polling_interval_sec),
            stability_checks=StabilityChecks(cfg.stability_checks),
            min_text_length=MinTextLength(cfg.min_text_length),
            cancel_event=request.cancel_event,
        )
        return RuntimeResponse(response_text=verdict.text, verdict=verdict.verdict)

    def _upload(self, request: RuntimeRequest) -> RuntimeResponse:
        """Attach the named file; the capability validates it pre-flight."""
        if not str(request.filepath).strip():
            raise QwenCliError("upload verb requires request.filepath (the file to attach)")
        accepted = self._uploader.upload_attachment(
            page=cast(Page, request.page),
            filepath=cast(Path, request.filepath),
            emitter=cast(LifecycleEmitter | None, request.emitter),
            web_loaded=HeadlessFlag(bool(request.web_loaded)),
        )
        return RuntimeResponse(accepted=bool(accepted))

    def _persist(self, request: RuntimeRequest) -> RuntimeResponse:
        """Write the artifact to the operator's named destination."""
        if request.output_path is None or not str(request.output_path).strip():
            raise QwenCliError("persist verb requires request.output_path (where the artifact is written)")
        ctx = request.ctx if request.ctx is not None else RunContext()
        out_path = cast(Path, request.output_path)
        self._saver.write_output(
            path=out_path,
            content=ResponseText(str(request.content)),
            ctx=ctx,
            src=cast(FilePath, out_path),
            dur=request.dur,
            input_chars=request.input_chars,
            output_chars=request.output_chars,
            config=request.config,
        )
        return RuntimeResponse(
            saved_path=cast(Path, request.output_path), response_text=ResponseText(str(request.content))
        )


__all__ = ["PromptRuntimeOrchestrator"]
