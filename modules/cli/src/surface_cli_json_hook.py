"""CLI surface: shared JSON envelope and console-status helpers.

Smart surface helpers (no domain imports): the fixed-key failure envelope
every ``--json`` surface funnels through, the ``[ERROR]`` / ``[WARN]``
stderr channels, the status-glyph vocabulary shared by the report surfaces,
and the display-width-aware truncation helper the pool tables render
through. Glyphs are emitted unpainted; the Textual TUI layer owns all ANSI
color.
"""

from __future__ import annotations

import json
import sys
import unicodedata

#: Failure exit code shared by every ``--json`` surface: the fixed-key
#: envelope and ``error_code`` never diverge in exit status.
EXIT_FAILURE = 1

#: Canonical status glyphs: ``✓ / ✗ / ⚠`` for results, ``● / ◐ / ○`` for
#: health, ``…`` for pending. ASCII-safe keys so surfaces stay greppable.
STATUS_GLYPHS: dict[str, str] = {
    "ok": "✓",
    "fail": "✗",
    "warn": "⚠",
    "pending": "…",
    "health_ok": "●",
    "health_limited": "◐",
    "health_unknown": "○",
}

_ERROR_PREFIX = "[ERROR]"
_WARN_PREFIX = "[WARN]"

#: Glyphs that render two columns wide in the CLI's monospaced fonts even
#: though ``unicodedata.east_asian_width`` reports them ``A`` (ambiguous):
#: the geometric health glyphs and the heavy box-drawing rule. Named here so
#: :func:`display_width` matches the terminal, not the Unicode property
#: table. The ellipsis ``…`` and the result markers ``✓ / ✗ / ⚠`` render one
#: column and stay out of the table so :func:`_fit` can trade one column of
#: content for the marker.
_TWO_COLUMN_CHARS = frozenset("●◐○━")

_WIDE_CATEGORIES = ("W", "F")


def _char_width(char: str) -> int:
    """Return the terminal columns one character occupies (2 for wide glyphs)."""
    if char in _TWO_COLUMN_CHARS:
        return 2
    return 2 if unicodedata.east_asian_width(char) in _WIDE_CATEGORIES else 1


def print_error(msg: str) -> None:
    """Print ``[ERROR] {msg}`` on stderr — the non-JSON failure channel."""
    print(f"{_ERROR_PREFIX} {msg}", file=sys.stderr)


def print_warn(msg: str) -> None:
    """Print ``[WARN] {msg}`` on stderr — the non-fatal degradation channel."""
    print(f"{_WARN_PREFIX} {msg}", file=sys.stderr)


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


def display_width(text: str) -> int:
    """Return the number of terminal columns *text* occupies.

    ``len()`` undercounts wide glyphs (``●``, ``◐``, ``━``, CJK): each renders
    two columns while counting as one character, so a width computed from the
    character count overflows the terminal.
    """
    return sum(_char_width(char) for char in text)


def _display_slice(text: str, width: int) -> str:
    """Return the leading substring of *text* covering *width* display columns."""
    consumed = 0
    for index, char in enumerate(text):
        if consumed + _char_width(char) > width:
            return text[:index]
        consumed += _char_width(char)
    return text


def _fit(text: str, width: int) -> str:
    """Return *text* clamped to *width* display columns with a ``…`` marker.

    The marker is itself one display column, so a fitted string's display
    width is exactly *width* (``width - 1`` of content plus ``…``).
    """
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    if width == 1:
        return "…"
    return _display_slice(text, width - 1) + "…"


__all__ = [
    "EXIT_FAILURE",
    "STATUS_GLYPHS",
    "_fail_json",
    "display_width",
    "status_glyph",
]
