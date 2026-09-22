"""Taxonomy definitions for qwen-web domain errors and error categories."""

from __future__ import annotations


class QwenCliError(RuntimeError):
    """Base exception for qwen-cli errors."""


class AuthRequiredError(QwenCliError):
    """Raised when authentication challenge/login is required in headless mode."""


class ModelSwitchError(QwenCliError):
    """Raised when the hardcoded default model cannot be selected/verified."""


class PromptInjectionError(QwenCliError):
    """Raised when prompt text injection into Qwen input fails across all strategies."""


class RateLimitError(QwenCliError):
    """Raised when the server returns a rate-limit / throttling response.

    Attributes:
        retry_after_sec: Seconds the caller should wait before retrying, when
            the throttling source can estimate it. ``None`` when unknown.

    """

    def __init__(self, message: str, retry_after_sec: float | None = None) -> None:
        """Store the human-readable reason plus an optional retry hint."""
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class CircuitBreakerOpenError(QwenCliError):
    """Raised when the circuit breaker trips due to consecutive failures."""


class BrowserLaunchError(QwenCliError):
    """Raised when the browser context cannot be launched."""


class ElementNotFoundError(QwenCliError):
    """Raised when a required DOM element is not found on the page."""


class NetworkTimeoutError(QwenCliError):
    """Raised when network operation times out or drops."""


class ResponseDetectionTimeoutError(QwenCliError):
    """Raised when a valid dispatch produces no detectable assistant response."""


class StuckDetectedError(QwenCliError):
    """Raised when the event-driven monitor sees no forward progress.

    Detection is event-based, not wall-clock: the stream monitor tracks the
    last forward event (thinking, streaming text change, or terminal
    completion). When no forward event arrives within ``stall_timeout_sec``,
    the run is classified stuck and this error is raised so callers can
    retry. Slow-but-alive generations keep emitting events and are never
    misclassified.
    """


class OutputValidationError(QwenCliError):
    """Raised when response content fails sanity check, such as a challenge page."""


class FileUploadError(QwenCliError):
    """Base exception for file upload errors."""


class FileValidationError(FileUploadError):
    """Raised when file pre-flight validation fails."""


class UploadFailureError(FileUploadError):
    """Raised when an attachment cannot be positively verified as uploaded."""


class UploadTimeoutError(FileUploadError):
    """Raised when Playwright interactions encounter an upload timeout."""


class UIInteractionError(FileUploadError):
    """Raised when upload UI elements cannot be found or interacted with."""


class RunCancelledError(QwenCliError):
    """Raised when a run is cancelled by a user-initiated cancellation request."""


class PipelineError(QwenCliError):
    """Base exception for queue processing pipeline errors."""


class QuarantineError(PipelineError):
    """Raised when a file fails all processing attempts and is moved to quarantine."""


class SendDispatchError(QwenCliError):
    """Raised when all send strategies fail."""


class OutputWriteError(QwenCliError):
    """Raised when writing output or metadata sidecar fails."""


class FolderCompileError(QwenCliError):
    """Raised when folder-to-markdown compilation fails."""


class FolderValidationError(FolderCompileError):
    """Raised when folder path validation fails."""


class FolderDepthExceededError(FolderCompileError):
    """Raised when folder recursion depth exceeds limit."""


class FolderEmptyError(FolderCompileError):
    """Raised when folder contains no compilable files."""


_ERROR_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("auth", "login", "captcha", "signin"), "auth"),
    (("model", "switch", "default model"), "model"),
    (("response detection", "response timeout", "stream timeout"), "response_timeout"),
    (("network", "connection", "timeout", "dns", "socket"), "network"),
    (("rate", "limit", "throttl", "429"), "rate_limit"),
    (("stuck", "stalled", "no forward progress"), "stuck"),
    (("browser", "launch", "dom", "playwright", "chromium"), "browser"),
    (("injection", "paste", "clipboard", "fill"), "injection"),
    (("parse", "empty", "no response", "timeout"), "parsing"),
    (("file", "ioerror", "disk", "read", "write"), "file_io"),
)


class ErrorCategory:
    """Categorize errors for dashboards and alerting."""

    @staticmethod
    def categorize(exc: BaseException) -> str:
        """Return the error category string."""
        exc_type = type(exc).__name__.lower()
        msg = str(exc).lower()
        for keywords, category in _ERROR_CATEGORY_RULES:
            if any(keyword in msg or keyword in exc_type for keyword in keywords):
                return category
        if isinstance(exc, (OSError, IOError)):
            return "file_io"
        return "other"


__all__ = [
    "QwenCliError",
    "AuthRequiredError",
    "ModelSwitchError",
    "PromptInjectionError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "BrowserLaunchError",
    "ElementNotFoundError",
    "NetworkTimeoutError",
    "ResponseDetectionTimeoutError",
    "StuckDetectedError",
    "OutputValidationError",
    "FileUploadError",
    "FileValidationError",
    "UploadFailureError",
    "UploadTimeoutError",
    "UIInteractionError",
    "RunCancelledError",
    "PipelineError",
    "QuarantineError",
    "SendDispatchError",
    "OutputWriteError",
    "FolderCompileError",
    "FolderValidationError",
    "FolderDepthExceededError",
    "FolderEmptyError",
    "ErrorCategory",
]
