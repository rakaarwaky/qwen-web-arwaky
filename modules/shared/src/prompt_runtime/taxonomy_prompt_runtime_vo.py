"""Prompt-runtime value objects and the aggregate request/response pair.

The five runtime verbs map one-to-one onto the five capability seams of
``modules/prompt_runtime`` — ``inject`` → ``IInjectionProtocol``,
``send`` → ``ISendProtocol``, ``watch`` → ``IStreamProtocol``,
``upload`` → ``IUploadProtocol``, ``persist`` → ``ISaverProtocol`` (the
protocol methods themselves stay in ``modules/shared/src/prompt/``,
because the runtime capabilities implement the seams the prompt feature
already declared). ``RuntimeRequest`` and ``RuntimeResponse`` are the
single pair ``IPromptRuntimeAggregate.execute`` accepts and returns, so
consumers depend on one stable seam.

Fields the chosen verb does not read stay at their defaults, exactly as
``taxonomy_prompt_vo.PromptRequest`` does, so a direct-prompt-shaped call
and a runtime-shaped call never trade arguments neither one consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from modules.shared.src.common.taxonomy_core_vo import (
    AttachmentPath,
    CancelToken,
    HeadlessFlag,
    MessageCount,
    OutputChars,
    OutputPath,
    PromptText,
    ResponseText,
    RunContext,
    TimeoutSec,
)
from modules.shared.src.prompt.taxonomy_prompt_vo import ExtractionVerdict

#: Which runtime verb a ``RuntimeRequest`` asks for. The agent behind
#: ``IPromptRuntimeAggregate`` routes each one to the matching capability's
#: public method; a verb is added here, never as a second aggregate method.
RuntimeVerb = Literal[
    "inject",
    "send",
    "watch",
    "upload",
    "persist",
]


@dataclass(frozen=True)
class RuntimeRequest:
    """One runtime verb plus everything the agent needs to route it.

    ``page`` is the live Playwright page for the DOM-driving verbs, kept
    as ``object`` (like ``PromptRequest.page``) so the taxonomy layer
    never imports Playwright. The ``config`` / ``emitter`` /
    ``observability`` slots are the caller-supplied services a verb may
    need — an ``InjectorConfig`` for ``inject``, a ``SenderConfig`` for
    ``send``, a ``StreamerConfig`` for ``watch``, the lifecycle emitter
    for ``send``/``watch``, the run context for ``persist``.
    """

    verb: RuntimeVerb
    page: object = None
    prompt: PromptText = PromptText("")
    #: Attachment source for ``upload``; also the recorded source file
    #: for ``persist``.
    filepath: Path | str = ""
    attachment: Path | AttachmentPath | str | None = None
    #: Destination for ``persist`` — the artifact lands exactly here.
    output_path: Path | OutputPath | str | None = None
    timeout_sec: TimeoutSec = TimeoutSec(120)
    msg_count_before: MessageCount = MessageCount(0)
    #: Response body for ``persist``.
    content: ResponseText = ResponseText("")
    #: Run traceability for ``persist``; defaults to a fresh run context.
    ctx: RunContext | None = None
    dur: float = 0.0
    input_chars: int = 0
    output_chars: OutputChars = OutputChars(0)
    #: ``send``'s parse gate: dispatch is refused while False, mirroring
    #: ``ISendProtocol.click_send``'s ``document_parsed`` argument.
    document_parsed: bool = True
    #: ``upload``'s web-readiness gate, mirroring
    #: ``IUploadProtocol.upload_attachment``'s ``web_loaded`` argument.
    web_loaded: HeadlessFlag = HeadlessFlag(True)
    config: object = None
    emitter: object = None
    observability: object = None
    cancel_event: CancelToken | None = None


@dataclass(frozen=True)
class RuntimeResponse:
    """What a runtime verb produced.

    The verbs return different natural facts, and the verb methods all
    answer this type directly — the same deliberate looseness
    ``PromptResponse`` carries, because the five capabilities are wired
    once per container and no second consumer distinguishes a narrower
    outcome shape. ``response_text`` and ``verdict`` describe what the
    ``watch`` verb observed (the verdict is the extraction verdict
    FR-PROMPT-006 defines); ``accepted`` is the ``upload`` verdict;
    ``message_count`` is the post-dispatch turn count from ``send``;
    ``saved_path`` is where ``persist`` wrote the artifact.
    """

    response_text: ResponseText | None = None
    verdict: ExtractionVerdict | None = None
    accepted: bool = True
    saved_path: Path | None = None
    message_count: MessageCount = MessageCount(0)


__all__ = [
    "ExtractionVerdict",
    "PromptText",
    "ResponseText",
    "RuntimeRequest",
    "RuntimeResponse",
    "RuntimeVerb",
]
