"""CLI surface: shared JSON envelope and console-status helpers.

Smart surface helpers (no domain imports): the fixed-key failure envelope
every ``--json`` surface funnels through, the ``[ERROR]`` stderr channel,
and the status-glyph vocabulary shared by the report surfaces. Glyphs are
emitted unpainted; the Textual TUI layer owns all ANSI color.

UX-3-002: ``STATUS_GLYPHS`` is declared once in the shared Taxonomy layer
(:mod:`modules.shared.src.common.taxonomy_core_constant`) and re-exported
here so the CLI and the TUI read the same object instead of each carrying
a literal that drifts.
"""

from __future__ import annotations

import json
import sys

from modules.shared.src.common.taxonomy_core_constant import STATUS_GLYPHS

#: Failure exit code shared by every ``--json`` surface: the fixed-key
#: envelope and ``error_code`` never diverge in exit status.
EXIT_FAILURE = 1

_ERROR_PREFIX = "[ERROR]"


def print_error(msg: str) -> None:
    """Print ``[ERROR] {msg}`` on stderr — the non-JSON failure channel."""
    print(f"{_ERROR_PREFIX} {msg}", file=sys.stderr)


def status_glyph(key: str) -> str:
    """Return the glyph for *key*, unpainted (the TUI layer owns color)."""
    return STATUS_GLYPHS.get(key, key)


def _fail_json(message: str, error_code: str, json_output: bool) -> int:
    """Emit one failure on the canonical channel; always exit :data:`EXIT_FAILURE`.

    With *json_output* the fixed-key envelope
    ``{"success": false, "message": str, "error_code": str}`` goes to stdout;
    otherwise ``[ERROR] {message}`` goes to stderr.
    """
    if json_output:
        print(json.dumps({"success": False, "message": message, "error_code": error_code}, indent=2))
    else:
        print_error(message)
    return EXIT_FAILURE


__all__ = [
    "EXIT_FAILURE",
    "STATUS_GLYPHS",
    "_fail_json",
    "print_error",
    "status_glyph",
]
