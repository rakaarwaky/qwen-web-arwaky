"""Core capability protocols (contract layer).

Taxonomy layer (contract(protocol)): pure ABCs, signatures use VOs.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import ElementHandle, Page

from modules.shared.src.taxonomy_core_constant import MAX_FOLDER_DEPTH, MAX_IMPORT_DEPTH
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_event import EventMessage, LifecycleEvent, QwenEventType
from modules.shared.src.taxonomy_core_vo import (
    ExitCode,
    FilePath,
    FileSizeBytes,
    ForceFlag,
    HeadlessFlag,
    InjectorConfig,
    JobId,
    JobLimit,
    JobName,
    JobRecord,
    LoggerName,
    MaxFileSizeMb,
    MessageCount,
    MinTextLength,
    OutputChars,
    OutputPath,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    RunId,
    RunState,
    SlotInputValue,
    SlotRunPlan,
    StabilityChecks,
    StatusRecordVO,
    TimeoutSec,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)

# A lifecycle observer receives every emitted pipeline event; surfaces use
# it to render event-level status (thinking / streaming / prompting) in the
# TUI slot badge and overview table.
LifecycleObserver = Callable[[QwenEventType, LifecycleEvent], None]


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


class IFolderCompileProtocol(ABC):
    """Folder-to-markdown compilation capability contract."""

    @abstractmethod
    def compile_folder(
        self,
        folder_path: Path,
        output_path: Path | None = None,
        max_depth: int = MAX_FOLDER_DEPTH,
        import_depth: int = MAX_IMPORT_DEPTH,
        include_imports: bool = True,
        boundary_root: Path | None = None,
    ) -> Path:
        """Compile folder contents to a single markdown file.

        Args:
            folder_path: Directory to compile.
            output_path: Optional output file path. Auto-generated if None.
            max_depth: Maximum recursion depth.
            import_depth: Maximum number of hops for resolving external
                imports/links beyond the first-hop files linked from the
                folder.  With the default of 1, only files linked directly
                from in-folder documents are included; transitive
                (second-hop) links are not followed.
            include_imports: Follow imports/links of folder files and include
                external dependencies (cycle-safe, bounded hops).
            boundary_root: Confinement boundary for import resolution.
                Resolved imports outside this root are refused because the
                compiled output is uploaded to a third-party service.
                Defaults to the ``QWEN_WORKSPACE_ROOT`` env var when set
                (matching the MCP workspace boundary), else the scanned
                folder's parent.

        Returns:
            Path to the compiled markdown file.
        """

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""


class IFolderToAttachmentProtocol(ABC):
    """Folder-to-attachment resolution capability contract."""

    @abstractmethod
    def resolve_to_attachment(
        self,
        path: Path,
        max_depth: int = MAX_FOLDER_DEPTH,
        import_depth: int = MAX_IMPORT_DEPTH,
    ) -> Path:
        """Resolve a path to an attachment-ready file (compile folders to markdown)."""

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""


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
        cancel_event: Any | None = None,
    ) -> ResponseText | None:
        """Wait for a stable assistant response; return its text.

        ``cancel_event`` is an optional per-run ``threading.Event``; when set
        the wait loop raises ``RunCancelledError`` instead of continuing to
        poll.
        """

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
    def setup_observability(self, log_path: Path, verbose: bool = False, attach_stderr: bool = True) -> None:
        """Bootstrap Sentry/OTel/structlog + global hooks.

        Parameters
        ----------
        attach_stderr:
            When False, skip attaching the stderr stream handler. Required by
            the interactive TUI so browser-callback logs do not corrupt the
            terminal canvas.
        """

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
    def attach_run_log(self, job_name: JobName, run_id: RunId) -> Path:
        """Attach a per-run JSONL log file under the jobs directory.

        Parameters
        ----------
        job_name : str
            Logical job/run name (e.g. prompt file stem).
        run_id : RunId
            Unique run identifier used as file suffix and correlation key.

        Returns
        -------
        Path
            Path of the created per-run log file.
        """

    @abstractmethod
    def detach_run_log(self, run_id: RunId) -> None:
        """Detach and close the per-run log handler for the given run id."""

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

    @abstractmethod
    def rollback_to(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Rollback to a previously installed package version."""


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

    @abstractmethod
    def record_execution(self, success: bool) -> None:
        """Record a completed pipeline run for the rolling-window execution log."""


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


class ISlotRunPlanProtocol(ABC):
    """Contract for surface-agnostic slot-input resolution (surface → capability bridge)."""

    @abstractmethod
    def resolve_slot_run_plan(
        self,
        prompt_val: PromptText,
        file_val: PromptText,
        output_val: OutputPath,
        headless: HeadlessFlag,
    ) -> SlotRunPlan | SlotInputValue:
        """Resolve raw slot widget values into an executable run plan."""

    @abstractmethod
    def discover_batch_prompts(self, batch_dir: FilePath) -> object:
        """Return a list of prompt files, or an error descriptor, for a batch dir."""
        ...


class IRunCancelProtocol(ABC):
    """Contract for the shared targeted-cancel registry of in-flight runs.

    Implemented by ``capabilities_run_cancel_registry.CapabilitiesRunCancelRegistry``
    and injected into the prompt file / attachment / swarm orchestrators so
    that a cancel can stop one run's browser context without touching sibling
    runs.  Runs are addressed by their stable ``RunId`` — never by object
    identity of a ``threading.Event`` — so the handle cannot be invalidated
    by a collected or recycled event object.
    """

    @abstractmethod
    def register(self, run_state: RunState) -> None:
        """Track a newly started in-flight run."""

    @abstractmethod
    def release(self, run_state: RunState) -> None:
        """Drop the entry for a finished run."""

    @abstractmethod
    def cancel_run(self, run_id: RunId) -> None:
        """Stop the run identified by ``run_id`` and close its browser context."""

    @abstractmethod
    def cancel_by_event(self, cancel_event: threading.Event) -> None:
        """Cancel the run that was registered with this cancel event.

        Convenience for surface callers that only hold the original
        ``threading.Event``.  Delegates to the stable ``run_id`` lookup
        internally; safe no-op when the run has already finished.
        """

    @abstractmethod
    def set_active_bctx(self, run_id: RunId, bctx: Any) -> None:
        """Update the live browser context for a registered run (None clears it)."""

    @abstractmethod
    def active_bctx(self, run_id: RunId) -> Any:
        """Return the live browser context for ``run_id``, or None."""


__all__ = [
    "IUploadProtocol",
    "IFolderCompileProtocol",
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
    "ISlotRunPlanProtocol",
    "IRunCancelProtocol",
    "LifecycleObserver",
]
