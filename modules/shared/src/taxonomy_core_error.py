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
    """Raised when the server returns a rate-limit / throttling response."""


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
    "OutputValidationError",
    "FileUploadError",
    "FileValidationError",
    "UploadFailureError",
    "UploadTimeoutError",
    "UIInteractionError",
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
