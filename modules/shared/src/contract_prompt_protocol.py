"""Prompt-domain capability contracts (AES102 `_protocol`).

One file for the prompt feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IPromptInjectorProtocol``   → ``PromptInjector``    (inject / find_input)
- ``IPromptSenderProtocol``     → ``SendDispatcher``    (send / count / probe)
- ``IPromptStreamProtocol``     → ``StreamMonitor``     (wait / completion probes)
- ``IPromptSaverProtocol``      → ``OutputSaver``       (persist the response)
- ``IPromptUploaderProtocol``   → ``FileUploader``      (attachment upload / validation)
- ``IPromptFlowProtocol``       → ``PromptOrchestrator`` (inject → send → wait)

The outward export surface for outer layers is ``IPromptAggregate`` in
``contract_prompt_aggregate.py``, whose single ``execute`` takes a
``PromptRequest``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from threading import Event
from typing import Any

from playwright.sync_api import ElementHandle, Page

from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    FilePath,
    FileSizeBytes,
    InjectorConfig,
    InputChars,
    MaxFileSizeMb,
    MessageCount,
    MinTextLength,
    OutputChars,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    SenderConfig,
    StabilityCount,
    TimeoutSec,
)


class IPromptInjectorProtocol(ABC):
    """Chat-input injection capability contract."""

    @abstractmethod
    def inject_text(self, page: Page, text: PromptText | str, config: InjectorConfig | None = None) -> None:
        """Type *text* into the chat input on *page*.

        Raises:
            QwenCliError: When no input element can be found or verified.
        """
        ...

    @abstractmethod
    def find_input(
        self,
        page: Page,
        config: InjectorConfig | None = None,
    ) -> ElementHandle | None:
        """Return the chat input element on *page*, or None when absent."""
        ...


class IPromptSenderProtocol(ABC):
    """Send-button trigger and message-inspection capability contract."""

    @abstractmethod
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> None:
        """Click the send button on *page* once the parse gate clears.

        Raises:
            QwenCliError: When the send button never becomes enabled.
        """
        ...

    @abstractmethod
    def count_messages(self, page: Page) -> MessageCount:
        """Return how many assistant messages *page* shows."""
        ...

    @abstractmethod
    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Return the newest assistant message text, or None when empty."""
        ...


class IPromptStreamProtocol(ABC):
    """Assistant-response stream monitoring capability contract."""

    @abstractmethod
    def wait_for_response(
        self,
        page: Page,
        timeout_sec: TimeoutSec,
        msg_count_before: MessageCount,
        emitter: LifecycleEmitter,
        polling_interval_sec: PollIntervalSec = PollIntervalSec(1.0),
        stability_checks: StabilityCount = StabilityCount(4),
        min_text_length: MinTextLength = MinTextLength(1),
        dispatch_acknowledged: bool = True,
        baseline_text: ResponseText | None = None,
        cancel_event: Event | None = None,
    ) -> ResponseText | None:
        """Block until the assistant finishes answering, then return the text.

        *timeout_sec* is a wall-clock ceiling: when it elapses without a
        terminal generation event, the wait raises rather than returning a
        partial answer. *cancel_event* lets a caller stop the wait early.
        Returns None when the answer settles empty.

        Raises:
            ResponseDetectionTimeoutError: When no terminal response event
                arrives within *timeout_sec*.
            RunCancelledError: When *cancel_event* is set during the wait.
        """
        ...

    @abstractmethod
    def is_generation_complete(self, page: Page, *, thinking: bool | None = None) -> bool:
        """Return True when the assistant has finished generating.

        *thinking* may carry a pre-computed value to avoid a second DOM
        round-trip; omit it to probe on demand.
        """
        ...

    @abstractmethod
    def is_thinking_active(self, page: Page) -> bool:
        """Return True while the assistant is still thinking."""
        ...


class IPromptSaverProtocol(ABC):
    """Response output-saving capability contract."""

    @abstractmethod
    def write_output(
        self,
        path: Path,
        content: ResponseText,
        ctx: RunContext,
        src: FilePath,
        dur: PollIntervalSec,
        input_chars: InputChars,
        output_chars: OutputChars,
        config: Any | None = None,
    ) -> None:
        """Write *content* to *path* with a JSON traceability sidecar.

        Raises:
            OutputWriteError: When the file or its sidecar cannot be written.
        """
        ...


class IPromptUploaderProtocol(ABC):
    """Attachment-upload and file-verification capability contract."""

    @abstractmethod
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        config: dict[str, Any] | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: bool = True,
    ) -> bool:
        """Upload the file at *filepath* through the page's attachment control.

        Returns True when the attachment card is positively confirmed; on
        failure records the cause in ``last_error`` and returns False so a
        caller can inspect why the upload did not verify.
        """
        ...

    @abstractmethod
    def validate_file(self, filepath: Path, max_size_mb: MaxFileSizeMb = MaxFileSizeMb(100.0)) -> FileSizeBytes:
        """Return *filepath*'s size, refusing files above *max_size_mb*.

        Raises:
            QwenCliError: When the file is missing or exceeds the limit.
        """
        ...


class IPromptFlowProtocol(ABC):
    """Shared inject → send → wait capability contract."""

    @abstractmethod
    def dispatch_and_wait_for_response(
        self,
        page: Page,
        filepath: Path,
        prompt: PromptText | str,
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
        cancel_event: Event | None = None,
    ) -> ResponseText:
        """Inject *prompt*, click send, and wait for the AI response.

        Raises:
            ResponseDetectionTimeoutError: When no terminal response arrives
                within *timeout_sec* after MAX_ATTEMPTS retries.
            RunCancelledError: When *cancel_event* is set.
        """
        ...


__all__ = [
    "IPromptFlowProtocol",
    "IPromptInjectorProtocol",
    "IPromptSaverProtocol",
    "IPromptSenderProtocol",
    "IPromptStreamProtocol",
    "IPromptUploaderProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IPromptFlowProtocol": IPromptFlowProtocol,
    "IPromptInjectorProtocol": IPromptInjectorProtocol,
    "IPromptSenderProtocol": IPromptSenderProtocol,
    "IPromptStreamProtocol": IPromptStreamProtocol,
    "IPromptSaverProtocol": IPromptSaverProtocol,
    "IPromptUploaderProtocol": IPromptUploaderProtocol,
}
