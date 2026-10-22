"""Prompt-domain value objects and the aggregate request/response pair.

The five prompt capabilities each expose one named method per operation,
and each method returns the VO it already used — a concrete type per
method, never a union. ``PromptRequest`` and ``PromptResponse`` are the
single pair the aggregate's ``execute`` accepts and returns, so consumers
depend on one stable seam.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from modules.shared.src.common.taxonomy_core_event import LifecycleEvent, QwenEventType
from modules.shared.src.common.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    CancelToken,
    HeadlessFlag,
    MessageCount,
    OutputPath,
    PromptPath,
    PromptText,
    ResponseText,
    SenderConfig,
    TimeoutSec,
)

#: The extraction verdict a stream monitor reports for one response
#: (FR-PROMPT-006). ``complete`` reached a terminal generation event;
#: ``stalled`` was cut by the stall detector; ``incomplete`` ended any
#: other way without one.
ExtractionVerdict = Literal["complete", "stalled", "incomplete"]

#: Which prompt verb a ``PromptRequest`` asks for. The agent behind
#: ``IPromptAggregate`` routes each one to the matching protocol method.
PromptVerb = Literal[
    "process_direct_prompt",
    "process_prompt_file_only",
    "process_prompt_with_attachment",
    "request_cancel",
]


@dataclass(frozen=True)
class PromptRequest:
    """One prompt verb plus everything the agent needs to run it.

    Fields the chosen verb does not read stay at their defaults, so a
    direct prompt and a prompt-file run share one shape without either
    one passing arguments the other ignores.
    """

    verb: PromptVerb
    page: object = None
    prompt: PromptText = PromptText("")
    prompt_file: Path | PromptPath | str = ""
    attachment_file: Path | AttachmentPath | str | None = None
    output_file: Path | OutputPath | str | None = None
    headless: HeadlessFlag = HeadlessFlag(True)
    timeout_sec: TimeoutSec = TimeoutSec(120)
    sender_config: SenderConfig | None = None
    document_parsed: bool = True
    msg_count_before: MessageCount = MessageCount(0)
    cancel_event: CancelToken | None = None
    active_cfg: AppConfig | None = None
    emitter: object = None
    state: object = None
    observability: object = None
    event_observer: Callable[[QwenEventType, LifecycleEvent], None] | None = None
    #: Returns the pool session path chosen by session rotation, so a
    #: direct / file / attachment pipeline can run against the rotated
    #: profile instead of the default.
    session_resolver: Callable[[], Path | None] | None = None


@dataclass(frozen=True)
class StreamVerdict:
    """One assistant answer plus the verdict its extraction earned (FR-PROMPT-006).

    ``StreamMonitor.wait_for_response`` returns this so a caller can tell a
    complete response from one the stall detector cut; the adapters forward
    the verdict into ``PromptResponse.extraction_verdict``.
    """

    text: ResponseText
    verdict: ExtractionVerdict = "complete"


@dataclass(frozen=True)
class PromptResponse:
    """What a prompt verb produced.

    ``response_text`` carries the result message for the three processing
    verbs; ``extraction_verdict`` reports the monitor's verdict for the
    response the message describes (FR-PROMPT-001/002/003); ``cancelled``
    and ``pipelines_stopped`` report the outcome of ``request_cancel``
    (FR-PROMPT-004): how many in-flight pipelines the cancel actually
    stopped, so a terminal or absent run reports zero instead of a blanket
    success. The verb methods return this type directly — the verdict
    rides the call because the adapters are singletons wired once per
    container, and no second consumer distinguishes a narrower outcome
    shape.
    """

    response_text: ResponseText | None = None
    cancelled: bool = False
    pipelines_stopped: int = 0
    extraction_verdict: ExtractionVerdict | None = None


__all__ = [
    "ExtractionVerdict",
    "StreamVerdict",
    "PromptRequest",
    "PromptResponse",
    "PromptText",
    "PromptVerb",
]
