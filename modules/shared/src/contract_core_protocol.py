"""Core capability protocols (contract layer).

Taxonomy layer (contract(protocol)): pure ABCs, signatures use VOs.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from playwright.sync_api import ElementHandle, Page

from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_event import EventMessage
from modules.shared.src.taxonomy_core_vo import (
    ExitCode,
    FilePath,
    FileSizeBytes,
    ForceFlag,
    HeadlessFlag,
    InjectorConfig,
    JobId,
    JobLimit,
    JobRecord,
    LoggerName,
    MaxFileSizeMb,
    MessageCount,
    MinTextLength,
    OutputChars,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    RunId,
    StabilityChecks,
    StatusRecordVO,
    TimeoutSec,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class IUploadProtocol(ABC):
    """File upload capability contract (external Qwen Web UI adaptation)."""

    @abstractmethod
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        config: Any | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: HeadlessFlag = HeadlessFlag(True),
    ) -> bool:
        """Attach a file as an attachment. Returns True on success."""

    @abstractmethod
    def validate_file(self, filepath: Path, max_size_mb: MaxFileSizeMb = MaxFileSizeMb(100.0)) -> FileSizeBytes:
        """Pre-flight validation; returns file size in bytes."""


class IInjectionProtocol(ABC):
    """Prompt text injection capability contract."""

    @abstractmethod
    def find_input(self, page: Page, config: InjectorConfig | None = None) -> ElementHandle:
        """Locate the input element; raise if not found."""

    @abstractmethod
    def inject_text(self, page: Page, text: PromptText, config: InjectorConfig | None = None) -> None:
        """Inject prompt text via multi-strategy DOM injection."""


class ISendProtocol(ABC):
    """Send dispatcher capability contract."""

    @abstractmethod
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        config: Any | None = None,
        document_parsed: HeadlessFlag = HeadlessFlag(True),
    ) -> None:
        """Trigger the send action."""

    @abstractmethod
    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns."""

    @abstractmethod
    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Return the latest assistant response text."""


class IStreamProtocol(ABC):
    """Response streaming capability contract."""

    @abstractmethod
    def wait_for_response(
        self,
        page: Page,
        timeout_sec: TimeoutSec,
        msg_count_before: MessageCount,
        emitter: LifecycleEmitter,
        polling_interval_sec: PollIntervalSec = PollIntervalSec(1.0),
        stability_checks: StabilityChecks = StabilityChecks(4),
        min_text_length: MinTextLength = MinTextLength(1),
        dispatch_acknowledged: HeadlessFlag = HeadlessFlag(True),
        baseline_text: ResponseText | None = None,
    ) -> ResponseText | None:
        """Wait for a stable assistant response; return its text."""

    @abstractmethod
    def is_generation_complete(self, page: Page) -> bool:
        """True when Qwen has finished generating."""

    @abstractmethod
    def is_thinking_active(self, page: Page) -> bool:
        """True when Qwen is currently thinking/streaming."""


class IBrowserProtocol(ABC):
    """Browser lifecycle capability contract (Playwright adaptation)."""

    @abstractmethod
    def browser_session(self, cfg: Any) -> Any:
        """Context manager yielding a BrowserContext."""

    @abstractmethod
    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat and verify auth."""

    @abstractmethod
    def check_auth(self, page: Page) -> None:
        """Raise AuthRequiredError if not authenticated."""

    @abstractmethod
    def check_session(self, page: Page) -> bool:
        """Return True when the page contains the authenticated chat UI."""

    @abstractmethod
    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean chat state."""


class ISaverProtocol(ABC):
    """Output persistence capability contract."""

    @abstractmethod
    def write_output(
        self,
        path: Path,
        content: ResponseText,
        ctx: RunContext,
        src: FilePath,
        dur: float,
        input_chars: int,
        output_chars: OutputChars,
        config: Any | None = None,
    ) -> None:
        """Write processed output with metadata header + sidecar."""


class IObservabilityProtocol(ABC):
    """Observability capability contract (logging, tracing, hooks)."""

    @abstractmethod
    def setup_observability(self, log_path: Path) -> None:
        """Bootstrap Sentry/OTel/structlog + global hooks."""

    @abstractmethod
    def get_logger(self, name: LoggerName = LoggerName("qwen-cli")) -> Any:
        """Return a bound logger."""

    @abstractmethod
    def start_span(self, name: LoggerName) -> Any:
        """Return a span context manager (or no-op)."""

    @abstractmethod
    def bind_run_context(self, run_id: RunId, **extra: Any) -> None:
        """Bind run-scoped contextvars."""

    @abstractmethod
    def clear_run_context(self) -> None:
        """Clear run-scoped contextvars."""

    @abstractmethod
    def exit_code_for(self, exc: BaseException) -> ExitCode:
        """Map an unhandled exception to a process exit code."""

    @abstractmethod
    def install_excepthooks(self) -> None:
        """Install global exception handlers."""


class IUpdateProtocol(ABC):
    """Self-update & environment synchronization capability contract.

    Owns the full update pipeline: remote version discovery via GitHub Releases API,
    package upgrade via git pull / pip (with PEP 610 editable dev-repo detection),
    Playwright Chromium binary synchronization, and post-update installation-integrity
    health checks.
    """

    @abstractmethod
    def current_version(self) -> VersionString:
        """Return the installed package version ('unknown' when unresolvable)."""

    @abstractmethod
    def check_update(self) -> UpdateCheckResult:
        """Compare the installed version against the latest published release.

        Read-only: must never mutate the environment.
        """

    @abstractmethod
    def upgrade_package(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Upgrade (or reinstall, when forced) the package via pip."""

    @abstractmethod
    def sync_browser(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Synchronize Playwright Chromium browser binaries.

        When forced, cached Chromium builds are purged before re-downloading.
        """

    @abstractmethod
    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        Sequence: version check → package upgrade → browser sync → health checks.
        """


class IWorkspaceProtocol(ABC):
    """Workspace directory provisioning capability contract."""

    @abstractmethod
    def init_workspace(self, target_dir: FilePath) -> None:
        """Initialize workspace directories, SKILL.md, symlinks, and .gitignore."""


class IStatusProtocol(ABC):
    """Status file write/read capability contract."""

    @abstractmethod
    def write(self, **kwargs: Any) -> None:
        """Atomically write status to disk."""

    @abstractmethod
    def write_record(self, record: StatusRecordVO) -> None:
        """Atomically write a record to disk."""

    @abstractmethod
    def read(self) -> dict[str, Any] | None:
        """Read and return the current status record."""


class IMetricsProtocol(ABC):
    """In-memory metrics collection capability contract."""

    @abstractmethod
    def increment(self, key: EventMessage, amount: MessageCount = MessageCount(1)) -> None:
        """Increment a counter by the given amount."""

    @abstractmethod
    def get(self, key: EventMessage) -> MessageCount:
        """Return the current value of a counter."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of all counters."""


class IJobStorageProtocol(ABC):
    """Job persistence and state storage contract."""

    @abstractmethod
    def save_job(self, record: JobRecord) -> None:
        """Persist a job record to disk."""

    @abstractmethod
    def get_job(self, job_id: JobId | str) -> JobRecord | None:
        """Retrieve a job record by ID."""

    @abstractmethod
    def list_jobs(self, limit: JobLimit = JobLimit(10)) -> list[JobRecord]:
        """List recently recorded jobs."""


__all__ = [
    "IUploadProtocol",
    "IInjectionProtocol",
    "ISendProtocol",
    "IStreamProtocol",
    "IBrowserProtocol",
    "ISaverProtocol",
    "IObservabilityProtocol",
    "IUpdateProtocol",
    "IWorkspaceProtocol",
    "IStatusProtocol",
    "IMetricsProtocol",
    "IJobStorageProtocol",
]
