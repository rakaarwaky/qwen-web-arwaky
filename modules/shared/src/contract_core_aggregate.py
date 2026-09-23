"""Core aggregate contracts — business-logic APIs for all surfaces.

Taxonomy layer (contract(aggregate)): implemented by agent orchestrators and
consumed by CLI and MCP surfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    IObservabilityProtocol,
    ISendProtocol,
    IStreamProtocol,
    LifecycleObserver,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    HeadlessFlag,
    JobId,
    JobLimit,
    JobRecord,
    MessageCount,
    OutputPath,
    PromptPath,
    PromptText,
    ResponseText,
    SenderConfig,
    TimeoutSec,
)


class IPromptFlowAggregate(ABC):
    """Shared prompt dispatch/response-wait flow aggregate contract.

    Implemented by a shared agent flow orchestrator and consumed by the
    direct / file / attachment prompt orchestrators via dependency injection
    (agent-to-agent communication through a contract aggregate).
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
        cancel_event: Any | None = None,
    ) -> str:
        """Inject prompt, click send, and wait for the AI response.

        ``cancel_event`` is an optional ``threading.Event`` created per-run;
        when set, the flow raises ``RunCancelledError`` so the caller's
        browser context can be closed without touching sibling runs.
        """


class IDirectPromptAggregate(ABC):
    """Direct string prompt processing aggregate contract."""

    @abstractmethod
    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec = TimeoutSec(120),
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a direct text prompt string.

        ``event_observer`` optionally receives every emitted lifecycle event
        so a surface can render event-level status (thinking / streaming /
        prompting) for the run.
        """


class IPromptFileAggregate(ABC):
    """Prompt file processing aggregate contract."""

    @abstractmethod
    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
        cancel_event: Any | None = None,
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a prompt file from disk without attachment.

        ``event_observer`` optionally receives every emitted lifecycle event
        so a surface can render event-level status (thinking / streaming /
        prompting) for the run.
        """

    @abstractmethod
    def request_cancel(self, cancel_event: Any) -> None:
        """Register ``cancel_event`` (a ``threading.Event``) so setting it
        stops the matching in-flight run.

        Cancellation is part of the aggregate contract: surfaces and the
        Swarm orchestrator rely on it for per-slot/per-agent stops and must
        never reach for implementation-only methods via ``getattr``.
        Registering an event must not start, join, or block on any run.
        """


class IAttachmentPromptAggregate(ABC):
    """Attachment prompt processing aggregate contract."""

    @abstractmethod
    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
        cancel_event: Any | None = None,
        event_observer: LifecycleObserver | None = None,
    ) -> ResponseText:
        """Process a prompt file from disk with document attachment.

        ``cancel_event`` targets one browser run without affecting sibling
        jobs. ``event_observer`` optionally receives every emitted lifecycle
        event so a surface can render event-level status (thinking /
        streaming / prompting) for the run.
        """

    @abstractmethod
    def request_cancel(self, cancel_event: Any) -> None:
        """Register ``cancel_event`` (a ``threading.Event``) so setting it
        stops the matching in-flight run.

        Cancellation is part of the aggregate contract: surfaces and the
        Swarm orchestrator rely on it for per-slot/per-agent stops and must
        never reach for implementation-only methods via ``getattr``.
        Registering an event must not start, join, or block on any run.
        """


class ISessionAggregate(ABC):
    """Session aggregate contract for session validation and deletion."""

    @abstractmethod
    def validate_session(self, session_path: Path | None = None) -> tuple[bool, str]:
        """Return session validity and a human-readable status message."""

    @abstractmethod
    def delete_session(self, session_path: Path | None = None) -> ResponseText:
        """Delete the persistent login session at ``session_path``."""


class ISetupAggregate(ABC):
    """Setup aggregate contract for interactive manual login."""

    @abstractmethod
    def setup_session(
        self,
        wait_for_confirmation: Callable[[], None] | None = None,
        session_path: Path | None = None,
    ) -> ResponseText:
        """Validate or establish a persistent manual login session."""


class IJobManagerAggregate(ABC):
    """Job management aggregate contract for async execution and tracking."""

    @abstractmethod
    def submit_file_job(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> JobRecord:
        """Submit a prompt file job for asynchronous background processing."""

    @abstractmethod
    def submit_attachment_job(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> JobRecord:
        """Submit a prompt with attachment job for asynchronous background processing."""

    @abstractmethod
    def get_job_status(self, job_id: JobId | str) -> JobRecord | None:
        """Query status and details of a submitted job."""

    @abstractmethod
    def list_jobs(self, limit: JobLimit = JobLimit(10)) -> list[JobRecord]:
        """List recently submitted jobs."""

    @abstractmethod
    def shutdown(self) -> None:
        """Stop accepting background work and release the job executor."""


__all__ = [
    "IAttachmentPromptAggregate",
    "IDirectPromptAggregate",
    "IJobManagerAggregate",
    "IPromptFileAggregate",
    "IPromptFlowAggregate",
    "ISessionAggregate",
    "ISetupAggregate",
]
