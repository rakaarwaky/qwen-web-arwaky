"""Error-categorization and exit-code pure utilities.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from modules.shared.src.common.taxonomy_core_error import AuthRequiredError


def exit_code_for(exc: BaseException) -> int:
    """Map an unhandled exception to a process exit code.

    ``AuthRequiredError`` maps to 3 so code 2 stays argparse's exclusive
    usage-error signal (SA-3-02): a machine can tell a bad invocation from
    an expired session.
    """
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, AuthRequiredError):
        return 3
    return 1
