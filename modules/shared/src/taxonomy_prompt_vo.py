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
from threading import Event
from typing import Literal

from modules.shared.src.taxonomy_core_event import LifecycleEvent, QwenEventType
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    HeadlessFlag,
    MessageCount,
    OutputPath,
    PromptPath,
    PromptText,
    ResponseText,
    SenderConfig,
    TimeoutSec,
)

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
    cancel_event: Event | None = None
    active_cfg: AppConfig | None = None
    emitter: object = None
    state: object = None
    observability: object = None
    event_observer: Callable[[QwenEventType, LifecycleEvent], None] | None = None


@dataclass(frozen=True)
class PromptResponse:
    """What a prompt verb produced.

    ``response_text`` carries the assistant's answer for the three
    processing verbs; ``cancelled`` reports the outcome of
    ``request_cancel``.
    """

    response_text: ResponseText | None = None
    cancelled: bool = False


__all__ = [
    "PromptRequest",
    "PromptResponse",
    "PromptVerb",
]
