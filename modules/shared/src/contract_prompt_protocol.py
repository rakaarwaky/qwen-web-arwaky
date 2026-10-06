"""Prompt-domain capability contracts (AES102 `_protocol`).

One file for the prompt feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IDirectPromptProtocol``     → ``DirectPromptAdapter``
- ``IPromptFileProtocol``       → ``PromptFileAdapter``
- ``IAttachmentPromptProtocol`` → ``AttachmentPromptAdapter``
- ``IPromptFlowProtocol``       → ``PromptFlowDispatcher``

The outward entry point, ``IPromptAggregate``, is in
``contract_prompt_aggregate.py``.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Event

from playwright.sync_api import Page

from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    ISendProtocol,
    IStreamProtocol,
    LifecycleObserver,
)
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
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
from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse


class IDirectPromptProtocol(ABC):
    """Direct text-prompt capability: inject, send, and collect one answer."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a direct text prompt string.

        ``event_observer`` optionally receives every emitted lifecycle event
        so a surface can render event-level status (thinking / streaming /
        prompting) for the run.
        """
        ...


class IPromptFileProtocol(ABC):
    """Prompt-file capability: read a Markdown file, run it, persist the answer."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: Event | None = None,
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a prompt file from disk without attachment.

        ``cancel_event`` targets one browser run without affecting sibling
        jobs. ``event_observer`` optionally receives every emitted lifecycle
        event so a surface can render event-level status (thinking /
        streaming / prompting) for the run.
        """
        ...

    @abstractmethod
    def request_cancel(self, cancel_event: Event) -> None:
        """Register ``cancel_event`` so setting it stops the matching in-flight run.

        Cancellation is part of the seam so surfaces and the Swarm
        orchestrator can stop per-slot work without reaching for
        implementation-only methods. Registering an event must not start,
        join, or block on any run.
        """
        ...


class IAttachmentPromptProtocol(ABC):
    """Attachment-prompt capability: upload a document, then run the prompt file."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: Event | None = None,
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a prompt file from disk with document attachment.

        ``cancel_event`` targets one browser run without affecting sibling
        jobs. ``event_observer`` optionally receives every emitted lifecycle
        event so a surface can render event-level status (thinking /
        streaming / prompting) for the run.
        """
        ...

    @abstractmethod
    def request_cancel(self, cancel_event: Event) -> None:
        """Register ``cancel_event`` so setting it stops the matching in-flight run.

        Cancellation is part of the seam so surfaces and the Swarm
        orchestrator can stop per-slot work without reaching for
        implementation-only methods. Registering an event must not start,
        join, or block on any run.
        """
        ...


class IPromptFlowProtocol(ABC):
    """Shared prompt dispatch/response-wait flow capability.

    One method: the inject → send → wait flow with retry and rollback.
    Implemented by ``PromptFlowDispatcher`` and consumed by the direct,
    file, and attachment prompt adapters via dependency injection.
    """

    @abstractmethod
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
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Inject the prompt, send it, and wait for the AI response.

        Retries on rate-limit and response-timeout errors; raises
        ``RunCancelledError`` when ``cancel_event`` is set.
        """
        ...


__all__ = [
    "IAttachmentPromptProtocol",
    "IDirectPromptProtocol",
    "IPromptFileProtocol",
    "IPromptFlowProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IAttachmentPromptProtocol": IAttachmentPromptProtocol,
    "IDirectPromptProtocol": IDirectPromptProtocol,
    "IPromptFileProtocol": IPromptFileProtocol,
    "IPromptFlowProtocol": IPromptFlowProtocol,
}
