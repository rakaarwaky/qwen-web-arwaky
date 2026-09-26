"""Core aggregate contracts — business-logic APIs for all surfaces.

Taxonomy layer (contract(aggregate)): implemented by agent orchestrators and
consumed by CLI and MCP surfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractContextManager
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
    Mode,
    OutputPath,
    PromptPath,
    PromptText,
    ResponseText,
    SenderConfig,
    TimeoutSec,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
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
    def delete_session(self, session_path: Path | None = None, *, force: bool = False) -> ResponseText:
        """Delete the persistent login session at ``session_path``.

        ``force`` bypasses the no-backup guard that protects the master profile
        from accidental deletion (issue #300).
        """


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


class IBrowserAggregate(ABC):
    """Authenticated browser session aggregate contract.

    Wraps the low-level ``IBrowserProtocol`` so consumers open an
    authenticated chat page through one call instead of repeating the
    launch → navigate → auth-check sequence. A session that cannot be
    authenticated raises rather than yielding a page the caller must
    validate, so no orchestrator skips the auth check by accident.
    """

    @abstractmethod
    def open_session(self, cfg: AppConfig) -> AbstractContextManager[Page]:
        """Context manager yielding an authenticated ``chat.qwen.ai`` page.

        The context owns the Chromium process group: entering launches the
        persistent context, navigates to the chat, and proves the saved
        session is still authenticated; exiting tears the browser down
        even when the body raises.
        """

    @abstractmethod
    def check_session(self, page: Page) -> bool:
        """Return True when ``page`` already shows the authenticated chat UI."""


class IConfigAggregate(ABC):
    """Runtime configuration aggregate contract.

    Replaces direct calls to the config-building free function. Every
    orchestrator that needs an ``AppConfig`` receives this aggregate so
    environment-derived decisions (sandbox probing, request-timeout
    override) have one injection point instead of a module-level import.
    """

    @abstractmethod
    def for_mode(
        self,
        mode: Mode = Mode(""),
        *,
        input_path: Path | None = None,
        output_path: Path | None = None,
        headless: bool = True,
        session_path: Path | None = None,
        prompt_file: Path | None = None,
        file_path: Path | None = None,
        model: str = "",
        **overrides: Any,
    ) -> AppConfig:
        """Build an ``AppConfig`` for ``mode`` with the given overrides.

        Unspecified fields fall back to the shared defaults, and
        environment switches still win over the passed values, so callers
        cannot bypass the sandbox or timeout policy by constructing a
        config directly.
        """

    @abstractmethod
    def request_timeout_sec(self) -> TimeoutSec:
        """Return the effective response-wait ceiling in seconds."""


class IUpdateAggregate(ABC):
    """Self-update aggregate contract for the update command surface.

    Sits between the update surface and ``IUpdateProtocol`` so the surface
    depends on an aggregate rather than the capability protocol, keeping
    the rollback decision (run the post-update health gate, then restore
    the previous version when it fails) in the agent layer.
    """

    @abstractmethod
    def check(self) -> UpdateCheckResult:
        """Report whether a newer release is published, without mutating anything."""

    @abstractmethod
    def perform(self, *, force: bool = False) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        When the post-update health gate fails, the aggregate restores the
        previous version before returning, so the report's ``rolled_back``
        and ``rollback_status`` fields describe work the caller can trust.
        """

    @abstractmethod
    def rollback(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Restore ``previous_version`` and return the per-step outcome."""


__all__ = [
    "IAttachmentPromptAggregate",
    "IBrowserAggregate",
    "IConfigAggregate",
    "IDirectPromptAggregate",
    "IJobManagerAggregate",
    "IPromptFileAggregate",
    "IPromptFlowAggregate",
    "ISessionAggregate",
    "ISetupAggregate",
    "IUpdateAggregate",
]
