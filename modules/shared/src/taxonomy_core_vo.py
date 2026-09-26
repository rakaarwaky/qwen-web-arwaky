"""Core qwen-web domain value objects: brand (NewType) types, run context,
Core value objects only.

Taxonomy layer (taxonomy(vo)): immutable value contracts and brand aliases — no I/O.
Lifecycle events live in taxonomy_core_event; domain errors live in taxonomy_core_error.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import NewType, TypeAlias

PromptText = NewType("PromptText", str)
PromptPath = NewType("PromptPath", Path)
AttachmentPath = NewType("AttachmentPath", Path)
FolderPath = NewType("FolderPath", Path)
InputPath = NewType("InputPath", Path)
OutputPath = NewType("OutputPath", Path)
FilePath = NewType("FilePath", Path)
RunId = NewType("RunId", str)
RunIdHex = NewType("RunIdHex", str)
CompileDepth = NewType("CompileDepth", int)
JobName = NewType("JobName", str)
RunContextId = NewType("RunContextId", str)
MessageCount = NewType("MessageCount", int)
FailureCategory = NewType("FailureCategory", str)
FailureCategoryCounts = NewType("FailureCategoryCounts", Mapping[str, int])
ResponseText = NewType("ResponseText", str)
StabilityCount = NewType("StabilityCount", int)
TimeoutSec = NewType("TimeoutSec", int)
PollIntervalSec = NewType("PollIntervalSec", float)
HeadlessFlag = NewType("HeadlessFlag", bool)
Mode = NewType("Mode", str)
EventName: TypeAlias = str
EventTimestamp: TypeAlias = float
EventId: TypeAlias = str
EventDetailsMapping: TypeAlias = Mapping[str, object]
EventOrderMapping: TypeAlias = dict[object, int]
RetryWaitSec = NewType("RetryWaitSec", float)
ErrorReason = NewType("ErrorReason", str)


class EventDetails(dict[str, object]):
    """Concrete detail mapping retained for legacy runtime construction."""


class EventOrderMap(dict[object, int]):
    """Concrete event-order mapping retained for legacy runtime behavior."""


class EventSequenceVO(tuple[object, ...]):
    """Ordered tuple of QwenEventType values.

    Used by taxonomy entities to hold a configured event sequence without
    leaking a raw ``tuple`` primitive (AES401).
    """

    def __new__(cls, seq: object) -> EventSequenceVO:
        # ``tuple`` construction requires the iterable at creation time;
        # the public type is deliberately ``object`` so callers in the
        # entity layer can pass either a VO or a plain tuple/list.
        if isinstance(seq, (list, tuple)):
            return super().__new__(cls, seq)
        return super().__new__(cls, (seq,))


class ProcessingStatus(str, Enum):
    """Terminal status for one queue item."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ProcessingOutcome:
    """Result of one processing attempt, including quarantine details."""

    status: ProcessingStatus
    error: str | None = None


JobId = NewType("JobId", str)
JobLimit = NewType("JobLimit", int)
AsyncRunFlag = NewType("AsyncRunFlag", bool)


@dataclass(frozen=True)
class JobRecord:
    """Immutable representation of a background job state.

    Attribute provenance (every field and its producing operation):

    - ``job_id``, ``created_at`` — written by ``submit_file_job`` /
      ``submit_attachment_job`` at DISPATCH_ACKNOWLEDGED.
    - ``latest_event`` — advanced by each ``_save_*`` transition.
    - ``completed`` — ``False`` at submit/started, ``True`` at
      ``_save_success`` / ``_save_failure`` / zombie reconciliation.
    - ``started_at`` — set by ``_save_started`` in the worker.
    - ``completed_at``, ``duration_sec`` — set by the terminal ``_save_*``.
    - ``input_file``, ``attachment_file``, ``output_file`` — set by the
      submit helpers, refined by ``_save_started`` (attachment path).
    - ``owner_pid`` — set to the submitting process PID; cleared from
      consideration only by terminal states.
    - ``heartbeat_at`` — refreshed by ``_save_started`` for lease checks.
    - ``error`` — set by ``_save_failure`` or zombie reconciliation.
    - ``result_preview`` — set by ``_save_success``.

    ``prompt_text`` was removed: no producer ever wrote it, and the job
    manager exposes no direct-text submit path (SA-2-01 / issue #375).
    """

    job_id: str
    created_at: str
    latest_event: str | None = None
    completed: bool = False
    started_at: str | None = None
    completed_at: str | None = None
    duration_sec: float | None = None
    input_file: str | None = None
    attachment_file: str | None = None
    output_file: str | None = None
    owner_pid: int | None = None
    heartbeat_at: str | None = None
    error: str | None = None
    result_preview: str | None = None


# ─── Brand types: timing & limits ─────────────────────────────
TypingDelayMs = NewType("TypingDelayMs", int)
WaitTimeoutMs = NewType("WaitTimeoutMs", int)
ClickTimeoutMs = NewType("ClickTimeoutMs", int)
BackoffDelaySec = NewType("BackoffDelaySec", float)
MaxRetries = NewType("MaxRetries", int)
StabilityChecks = NewType("StabilityChecks", int)
MinTextLength = NewType("MinTextLength", int)

# ─── Brand types: upload config ───────────────────────────────
MaxFileSizeMb = NewType("MaxFileSizeMb", float)
DropdownTimeoutMs = NewType("DropdownTimeoutMs", int)
OptionTimeoutMs = NewType("OptionTimeoutMs", int)
FileChooserTimeoutMs = NewType("FileChooserTimeoutMs", int)
CardRenderTimeoutMs = NewType("CardRenderTimeoutMs", int)

# ─── Brand types: saver config ────────────────────────────────
InputChars = NewType("InputChars", int)
OutputChars = NewType("OutputChars", int)
GenerateSidecarFlag = NewType("GenerateSidecarFlag", bool)
AtomicWriteFlag = NewType("AtomicWriteFlag", bool)

# ─── Brand types: browser & observability config ──────────────
ChromeProfile = NewType("ChromeProfile", str)
ConfigPath = NewType("ConfigPath", str)
DisableSandboxFlag = NewType("DisableSandboxFlag", bool)
UserAgent = NewType("UserAgent", str)
ServerName = NewType("ServerName", str)
ServiceName = NewType("ServiceName", str)
Environment = NewType("Environment", str)
TryEnterKeyFallbackFlag = NewType("TryEnterKeyFallbackFlag", bool)

# ─── Brand types: circuit breaker & rate limiter config ───────
FailureThreshold = NewType("FailureThreshold", int)
WindowSec = NewType("WindowSec", int)
MaxPerMinute = NewType("MaxPerMinute", int)

# ─── Brand types: stream & file validation config ────────────
FileSizeBytes = NewType("FileSizeBytes", int)

# ─── Brand types: observability & logging config ─────────────
LoggerName = NewType("LoggerName", str)
ExitCode = NewType("ExitCode", int)

# ─── Brand types: self-update & versioning ───────────────────
VersionString = NewType("VersionString", str)
ForceFlag = NewType("ForceFlag", bool)


@dataclass(frozen=True)
class UpdateCheckResult:
    """Read-only outcome of comparing the installed version to the latest release."""

    package_name: str
    current_version: str
    latest_version: str | None
    update_available: bool
    source: str  # "github" | "unavailable"

    error: str | None = None


@dataclass(frozen=True)
class UpdateStepResult:
    """Outcome of one update pipeline step (package upgrade, browser sync, health check)."""

    name: str
    executed: bool
    success: bool
    detail: str = ""
    skipped_reason: str | None = None


@dataclass(frozen=True)
class UpdateReport:
    """Aggregated immutable outcome of a full update run."""

    package_name: str
    previous_version: str
    latest_version: str | None
    source: str
    update_available: bool
    forced: bool
    changed: bool
    steps: tuple[UpdateStepResult, ...] = ()
    health_checks: tuple[UpdateStepResult, ...] = ()
    post_update_version: str | None = None
    healthy: bool = False
    message: str = ""
    rolled_back: bool = False
    # Issue #279: disambiguate what a failed update did with the previous
    # version. "rolled_back" alone cannot tell a partial package-restore from
    # a fully skipped rollback.
    rollback_status: str = "none"  # "full" | "partial" | "skipped" | "none"


@dataclass
class RunContext:
    """Run-scoped context with auto-generated run ID.

    Attributes
    ----------
    run_id : str
        Unique identifier: YYYYMMDD_HHMMSS_randomhex[:6].

    """

    run_id: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    )


_LEGACY_EVENT_EXPORTS = (
    "QwenEventType",
    "LifecycleEvent",
    "LifecycleCallback",
    "EventDetails",
    "EventMessage",
    "CallbackRegistry",
    "EVENT_DESCRIPTIONS",
    "PIPELINE_EVENT_SEQUENCE",
    "EVENT_ORDER",
    "EVENT_NETWORK_RECONNECTING",
    "EVENT_WEB_LOADED",
    "EVENT_FILE_UPLOADED",
    "EVENT_PROMPT_INJECTED",
    "EVENT_DOCUMENT_PARSED",
    "EVENT_SEND_CLICKED",
    "EVENT_DISPATCH_ACKNOWLEDGED",
    "EVENT_THINKING_STARTED",
    "EVENT_STREAMING_GENERATION",
    "EVENT_GENERATION_FINISHED",
    "EVENT_OUTPUT_COPIED",
)

_LEGACY_ERROR_EXPORTS = (
    "QwenCliError",
    "AuthRequiredError",
    "PromptInjectionError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "BrowserLaunchError",
    "ElementNotFoundError",
    "NetworkTimeoutError",
    "OutputValidationError",
    "FileUploadError",
    "FileValidationError",
    "UploadTimeoutError",
    "UIInteractionError",
    "PipelineError",
    "QuarantineError",
    "SendDispatchError",
    "OutputWriteError",
    "ErrorCategory",
)


def __getattr__(name: str) -> object:
    """Resolve event and error names lazily for legacy imports."""
    if name in _LEGACY_EVENT_EXPORTS:
        from . import taxonomy_core_event

        return getattr(taxonomy_core_event, name)
    if name in _LEGACY_ERROR_EXPORTS:
        from . import taxonomy_core_error

        return getattr(taxonomy_core_error, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass(frozen=True)
class SlotInputValue:
    """Invalid slot input from the TUI resolver; the surface only forwards the message.

    Mirrors the capabilities-layer ``SlotInputError`` shape but lives in the
    taxonomy so contract signatures stay domain-safe (no Capabilities import
    from the contract layer).
    """

    message: str


@dataclass(frozen=True)
class SlotRunPlan:
    """Validated TUI slot configuration ready to execute.

    Shared VO so the contract layer can name the success return type of
    ``ISlotRunPlanProtocol.resolve_slot_run_plan`` without importing the
    Capabilities layer.
    """

    prompt_path: Path
    attachment_path: Path | None
    config: AppConfig


@dataclass
class StatusRecordVO:
    """Status payload recorded for systemd/monitoring integration."""

    status: str
    mode: Mode
    headless: HeadlessFlag
    run_id: RunId | None = None
    files_processed: int = 0
    files_failed: int = 0
    cpu_sec: float | None = None
    error: str | None = None


def _validate_min(name: str, value: float | int, minimum: float | int) -> None:
    """Raise ValueError if value is below minimum."""
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")


@dataclass(frozen=True)
class UploadConfig:
    """Configuration options for file upload behavior."""

    max_file_size_mb: float = 100.0
    dropdown_timeout_ms: int = 5000
    option_timeout_ms: int = 3000
    file_chooser_timeout_ms: int = 8000
    card_render_timeout_ms: int = 5000
    parse_ready_timeout_ms: int = 120_000
    max_retries: int = 2
    backoff_delay_sec: float = 1.0

    dropdown_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".mode-select-open",
            "[class*='mode-select']",
        )
    )

    upload_option_selectors: Sequence[str] = field(
        default_factory=lambda: (
            "text='Upload attachment'",
            ".mode-select-dropdown-item:has-text('Upload attachment')",
            ".mode-select-dropdown-item[data-action='upload']",
            "[role='menuitem']:has-text('Upload attachment')",
            "text='Upload file'",
            "[data-testid*='upload' i]",
            "[aria-label*='upload' i]",
        )
    )

    parse_pending_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".fileitem-loading-icon",
            "[class*='loading']",
            "[class*='parsing']",
            "[class*='spin']",
            ".ant-spin",
        )
    )

    card_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".file-card-list",
            ".fileitem-btn",
            ".message-input-column-file",
            "[class*='file-card']",
            "[class*='file-item']",
            "[class*='fileitem']",
            "[class*='fileitem-file-name']",
            "[class*='file-content-info']",
        )
    )


DEFAULT_UPLOAD_CONFIG = UploadConfig()


@dataclass(frozen=True)
class InjectorConfig:
    """Configuration options for prompt text injection."""

    wait_timeout_ms: int = 10_000
    typing_delay_ms: int = 10
    verify_injection: bool = True
    input_selectors: Sequence[str] = field(
        default_factory=lambda: (
            "textarea.message-input-textarea",
            "textarea",
            "div[contenteditable='true']",
            "#chat-input",
            ".chat-input",
        )
    )


DEFAULT_INJECTOR_CONFIG = InjectorConfig()


@dataclass(frozen=True)
class ObservabilityConfig:
    """Configuration options for observability logging and tracing."""

    log_path: Path
    enable_sentry: bool = True
    enable_otel: bool = True
    environment: str = "production"


@dataclass(frozen=True)
class MCPToolResponse:
    """Structured response payload for MCP tool invocations."""

    success: bool
    data: str
    error: str | None = None


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration options for MCP server entrypoint."""

    server_name: str = "Qwen-Web"
    transport: str = "stdio"


@dataclass(frozen=True)
class QwenClientConfig:
    """Client operational configuration options."""

    timeout_sec: int = 120
    auto_attach_files: bool = True
    retry_upload_on_failure: bool = True


@dataclass(frozen=True)
class BrowserConfig:
    """Browser launch and session configuration options."""

    headless: bool = True
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    viewport_width: int = 1280
    viewport_height: int = 800
    block_media_assets: bool = True
    launch_timeout_sec: int = 30


@dataclass(frozen=True)
class SenderConfig:
    """Configuration options for send button interactions."""

    click_timeout_ms: int = 3000
    try_enter_key_fallback: bool = True


DEFAULT_SENDER_CONFIG = SenderConfig()


@dataclass(frozen=True)
class StreamerConfig:
    """Configuration options for AI response streaming and stability detection."""

    polling_interval_sec: float = 1.0
    stability_checks: int = 4
    min_text_length: int = 1


@dataclass(frozen=True)
class OutputMetadata:
    """Metadata payload recorded with processed output files."""

    run_id: str
    source_file: str
    processed_at: str
    duration_sec: float
    input_chars: int
    output_chars: int


@dataclass(frozen=True)
class SaverConfig:
    """Configuration options for saver module."""

    generate_sidecar: bool = True
    atomic_write: bool = True


DEFAULT_SAVER_CONFIG = SaverConfig()


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with defaults and validation."""

    input_path: Path
    output_path: Path
    session_path: Path
    log_path: Path | None = None
    mode: str = ""

    interval: int = 3
    timeout: int = 300
    headless: bool = False
    verbose: bool = False
    prompt_file: Path | None = None
    prompt_path: Path | None = None
    file_path: Path | None = None

    chrome_profile: str = "qwen-cli-profile"
    storage_state_file: Path | None = None
    # Least-privilege default: Chromium keeps its OS sandbox. It is dropped only
    # by an explicit opt-in (QWEN_DISABLE_SANDBOX=1) or by a detected
    # container that cannot provide user namespaces (issue #290).
    disable_sandbox: bool = False

    # Wall-clock ceiling on the response wait, enforced by the stream monitor
    # (``elapsed >= timeout_sec``). It is a ceiling, not an idle budget: a long
    # thinking phase emits no forward lifecycle event for its whole duration,
    # so a short ceiling aborts healthy runs. Run 20260926_014817_5cd3cc lost a
    # 244KB-attachment review to a 120s ceiling while Qwen was still thinking.
    # Override per environment with QWEN_REQUEST_TIMEOUT_SEC; the 300s stall
    # detector handles genuinely wedged runs inside this budget.
    request_timeout: int = 600
    poll_interval: float = 1.0
    streaming_timeout: int = 180
    inline_prompt: bool = False
    inline_prompt_text: str | None = None

    rate_limit_per_minute: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_window: int = 30

    # Issue #283: stakeholder-configurable model override. When set, the
    # browser adapter tries this model first; when the picker does not expose
    # it, the pipeline falls back to the first available model and logs a
    # WARNING instead of aborting.
    model: str = ""

    retry_failed: bool = False

    @property
    def status_path(self) -> Path:
        """Path to the JSON status file for monitoring."""
        from modules.shared.src.taxonomy_core_constant import STATUS_FILENAME

        return (self.log_path or Path(".")) / STATUS_FILENAME

    def validate(self) -> None:
        """Validate configuration before execution.

        Raises
        ------
        ValueError
            If any configuration value is invalid.

        """
        _validate_min("timeout", self.timeout, 30)
        _validate_min("poll_interval", self.poll_interval, 0.5)
        _validate_min("request_timeout", self.request_timeout, 10)
        _validate_min("rate_limit_per_minute", self.rate_limit_per_minute, 1)
        _validate_min("circuit_breaker_threshold", self.circuit_breaker_threshold, 2)

    def __post_init__(self) -> None:
        """Validate config on construction."""
        if self.log_path is None:
            from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG

            object.__setattr__(self, "log_path", DEFAULT_LOG)
        self.validate()


@dataclass
class RunState:
    """Per-run cancellation and browser-context state.

    One instance per orchestrator invocation.  ``cancel_event`` is owned by
    the caller when provided (targeted cancel), otherwise a private event is
    created for internal fail-fast checks.  ``active_bctx`` holds the live
    browser context so a cancel can close it; ``bctx_lock`` guards that field
    against concurrent set/clear from the run's worker thread.  ``run_id``
    is a stable identifier used by the run-cancel registry for lookups so
    cancellation never depends on event object identity across threads.
    """

    cancel_event: threading.Event = field(default_factory=threading.Event)
    active_bctx: object | None = None
    bctx_lock: threading.Lock = field(default_factory=threading.Lock)
    run_id: RunId = field(default_factory=lambda: RunId(uuid.uuid4().hex[:8]))

    def cancel_requested(self) -> bool:
        """True when the run's cancel event is set."""
        return self.cancel_event.is_set()


__all__ = [
    "PromptText",
    "InputPath",
    "FolderPath",
    "OutputPath",
    "FilePath",
    "RunId",
    "RunIdHex",
    "CompileDepth",
    "RunContextId",
    "MessageCount",
    "FailureCategory",
    "FailureCategoryCounts",
    "ResponseText",
    "StabilityCount",
    "TimeoutSec",
    "PollIntervalSec",
    "HeadlessFlag",
    "Mode",
    "EventName",
    "EventTimestamp",
    "EventId",
    "EventDetailsMapping",
    "EventOrderMapping",
    "RetryWaitSec",
    "ErrorReason",
    "EventDetails",
    "EventOrderMap",
    "EventSequenceVO",
    "ProcessingStatus",
    "ProcessingOutcome",
    "TypingDelayMs",
    "WaitTimeoutMs",
    "ClickTimeoutMs",
    "BackoffDelaySec",
    "MaxRetries",
    "StabilityChecks",
    "MinTextLength",
    "MaxFileSizeMb",
    "DropdownTimeoutMs",
    "OptionTimeoutMs",
    "FileChooserTimeoutMs",
    "CardRenderTimeoutMs",
    "InputChars",
    "OutputChars",
    "GenerateSidecarFlag",
    "AtomicWriteFlag",
    "ChromeProfile",
    "ConfigPath",
    "DisableSandboxFlag",
    "UserAgent",
    "ServerName",
    "ServiceName",
    "Environment",
    "TryEnterKeyFallbackFlag",
    "FailureThreshold",
    "WindowSec",
    "MaxPerMinute",
    "FileSizeBytes",
    "LoggerName",
    "ExitCode",
    "VersionString",
    "ForceFlag",
    "UpdateCheckResult",
    "UpdateStepResult",
    "UpdateReport",
    "RunContext",
    "StatusRecordVO",
    "UploadConfig",
    "DEFAULT_UPLOAD_CONFIG",
    "InjectorConfig",
    "DEFAULT_INJECTOR_CONFIG",
    "ObservabilityConfig",
    "MCPToolResponse",
    "MCPServerConfig",
    "SlotInputValue",
    "SlotRunPlan",
    "QwenClientConfig",
    "BrowserConfig",
    "SenderConfig",
    "DEFAULT_SENDER_CONFIG",
    "StreamerConfig",
    "OutputMetadata",
    "SaverConfig",
    "DEFAULT_SAVER_CONFIG",
    "AppConfig",
    "RunState",
]
