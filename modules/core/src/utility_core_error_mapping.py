"""Error mapping utilities.

Utility layer (utility_core_error_mapping): convert exceptions to ResponseText.
Stateless function consumed by Agent orchestrator for error handling.
"""

from __future__ import annotations

from modules.shared.src.taxonomy_core_vo import ResponseText

_CANCELLED = "RUN_CANCELLED"
_AUTH = "AUTH_REQUIRED"


def to_error_response(exc: BaseException) -> ResponseText:
    """Map an exception into a structured ResponseText error string."""
    name = type(exc).__name__
    if name == "AuthRequiredError":
        code = _AUTH
    elif name == "RunCancelledError":
        code = _CANCELLED
    else:
        code = name
    return ResponseText(f"ERROR [{code}]: {exc}")
