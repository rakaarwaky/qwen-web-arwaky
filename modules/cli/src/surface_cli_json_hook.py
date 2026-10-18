"""CLI surface: shared JSON envelope and console-status helpers.

Smart surface helpers (no domain imports): the fixed-key failure envelope
every ``--json`` surface funnels through, the ``[ERROR]`` / ``[WARN]``
stderr channels, and the status-glyph vocabulary plus terminal-fitted table
rendering shared by the report surfaces.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from typing import TextIO

#: Canonical status glyphs: ``✓ / ✗ / ⚠`` for results, ``● / ◐ / ○`` for
#: health, ``…`` for pending. ASCII-safe keys so surfaces stay greppable;
#: the ANSI paint is applied only on a TTY with NO_COLOR unset.
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
_RESET = "\033[0m"
_GLYPH_ANSI: dict[str, str] = {
    "ok": "\033[32m",
    "fail": "\033[31m",
    "warn": "\033[33m",
    "pending": "\033[90m",
    "health_ok": "\033[32m",
    "health_limited": "\033[33m",
    "health_unknown": "\033[90m",
}


def _color_enabled(stream: TextIO = sys.stdout) -> bool:
    """True only when *stream* is a TTY and ``NO_COLOR`` is unset."""
    return "NO_COLOR" not in os.environ and bool(getattr(stream, "isatty", lambda: False)())


def _colorize(text: str, key: str, stream: TextIO = sys.stdout) -> str:
    """Wrap *text* in the ANSI paint for *key* when the stream accepts color."""
    if not _color_enabled(stream):
        return text
    return f"{_GLYPH_ANSI[key]}{text}{_RESET}"


def status_glyph(key: str, *, stream: TextIO = sys.stdout) -> str:
    """Return the glyph for *key*, painted only on a color-capable stream."""
    glyph = STATUS_GLYPHS.get(key, key)
    return _colorize(glyph, key, stream=stream) if key in _GLYPH_ANSI else glyph


def print_error(msg: str) -> None:
    """Print ``[ERROR] {msg}`` on stderr — the non-JSON failure channel."""
    print(f"{_ERROR_PREFIX} {msg}", file=sys.stderr)


def print_warn(msg: str) -> None:
    """Print ``[WARN] {msg}`` on stderr — the non-fatal degradation channel."""
    print(f"{_WARN_PREFIX} {msg}", file=sys.stderr)


def _fail_json(message: str, error_code: str, json_output: bool) -> int:
    """Emit one failure on the canonical channel; always exit code 1.

    With *json_output* the fixed-key envelope
    ``{"success": false, "message": str, "error_code": str}`` goes to stdout;
    otherwise ``[ERROR] {message}`` goes to stderr.
    """
    if json_output:
        print(json.dumps({"success": False, "message": message, "error_code": error_code}, indent=2))
    else:
        print_error(message)
    return 1


def _fit(text: str, width: int) -> str:
    """Return *text* clamped to *width* columns with a ``…`` marker."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def _table_widths(rows: tuple[tuple[str, ...], ...], floors: tuple[int, ...], budget: int) -> list[int]:
    """Distribute *budget* across columns, honoring per-column *floors*.

    Natural content width wins while it fits; once it overflows only the
    widest columns are squeezed (never below their floor), so a narrow
    terminal shortens long values instead of dropping short ones. The
    inter-column separators are reserved before the squeeze runs, so a
    rendered row can never exceed the budget. Rows shorter than the column
    count contribute nothing, so a ragged row set cannot overflow the index.
    """
    counts = len(floors)
    widths = [floors[index] for index in range(counts)]
    for row in rows:
        for index in range(min(counts, len(row))):
            widths[index] = max(widths[index], len(row[index]))
    separators = max(0, counts - 1)
    # Repeatedly take one column from the widest until it fits or every
    # column sits at its floor. O(budget) at worst, and budget is bounded by
    # the terminal width, so this never scales with row count.
    for _ in range(max(0, sum(widths) + separators - budget)):
        candidates = [index for index in range(counts) if widths[index] > floors[index]]
        if not candidates:
            break
        widths[max(candidates, key=lambda index: widths[index])] -= 1
    return widths


def _render_table(
    rows: tuple[tuple[str, ...], ...],
    floors: tuple[int, ...],
    *,
    budget: int | None = None,
    rule: str = "─",
) -> str:
    """Render *rows* as a rule-bordered table fitted to the terminal width.

    The column budget defaults to ``shutil.get_terminal_size().columns`` and
    every cell passes through :func:`_fit`, so a table never wraps.
    """
    if budget is None:
        budget = shutil.get_terminal_size().columns
    widths = _table_widths(rows, floors, budget)
    separators = max(0, len(floors) - 1)
    rule_width = min(budget, sum(widths) + separators)
    lines = [rule * rule_width]
    for row in rows:
        lines.append(" ".join(_fit(cell, widths[index]).ljust(widths[index]) for index, cell in enumerate(row)))
    lines.append(rule * rule_width)
    return "\n".join(lines)


__all__ = [
    "STATUS_GLYPHS",
    "_colorize",
    "_fail_json",
    "_fit",
    "_render_table",
    "_table_widths",
    "print_error",
    "print_warn",
    "status_glyph",
]
