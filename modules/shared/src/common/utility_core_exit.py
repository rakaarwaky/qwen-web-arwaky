"""Error-categorization and exit-code pure utilities.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from modules.shared.src.common.taxonomy_core_error import AuthRequiredError


def exit_code_for(exc: BaseException) -> int:
    """Map an unhandled exception to a process exit code."""
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, AuthRequiredError):
        return 2
    return 1
