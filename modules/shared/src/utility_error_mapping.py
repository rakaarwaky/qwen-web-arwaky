"""Error mapping utilities.

Utility layer (utility_error_mapping): convert exceptions to ResponseText.
Stateless function consumed by Agent orchestrator for error handling.
"""

from __future__ import annotations

from modules.shared.src.taxonomy_core_error import AuthRequiredError, RunCancelledError
from modules.shared.src.taxonomy_core_vo import ResponseText

_CANCELLED = "RUN_CANCELLED"
_AUTH = "AUTH_REQUIRED"


def to_error_response(exc: BaseException) -> ResponseText:
    """Map an exception into a structured ResponseText error string.

    Classification uses ``isinstance`` against the taxonomy error hierarchy so
    subclasses (and subclasses defined by callers) keep their stable error
    codes — a ``type(exc).__name__`` string comparison would silently fall
    through to the raw class name as soon as an exception is subclassed,
    renamed, or re-exported under a different symbol.
    """
    if isinstance(exc, AuthRequiredError):
        code = _AUTH
    elif isinstance(exc, RunCancelledError):
        code = _CANCELLED
    else:
        code = type(exc).__name__
    return ResponseText(f"ERROR [{code}]: {exc}")
