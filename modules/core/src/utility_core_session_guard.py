"""Core utility: session deletion path safety guard.

Centralises the rules for whether a directory may be ``shutil.rmtree``'d
by the session orchestrator.  Extracted from ``agent_session_orchestrator``
so the negative tests (filesystem roots, Windows-style paths, near-root
paths) live in one place and both callers reuse the same logic.

AES201: utility layer imports taxonomy only.
"""

from __future__ import annotations

from pathlib import Path, PurePath

from modules.shared.src.taxonomy_core_constant import DEFAULT_SESSION

# A relative path resolves against the CWD; its part count is small even when
# it is not a real filesystem root.  The caller must always pass a *resolved*
# absolute path.
_PARTS_FLOOR = 3


def is_filesystem_root(path: PurePath) -> bool:
    """True when *path* is itself a filesystem root, not merely absolute.

    An absolute POSIX path always has ``parts[0] == "/"``, so testing the
    leading component alone would reject every valid path.  A root is a
    single-component path: POSIX ``/``, a bare separator, or a Windows drive
    root (``C:\\`` — whose ``parts`` is ``("C:\\",)``).
    """
    parts = path.parts
    if not parts:
        return True
    if len(parts) != 1:
        return False
    first = parts[0]
    if first in ("/", "\\"):
        return True
    # Windows drive root, spelled "C:\\" or "C:/" (PureWindowsPath keeps the
    # backslash form); also catches a POSIX host parsing the literal string.
    return len(first) == 3 and first[0].isalpha() and first[1:] in (":\\", ":/")


def is_safe_session_target(target: Path) -> bool:
    """Return True only when *target* is a deletable session directory.

    Safety rules, evaluated in order:

    1. *target* must be a resolved absolute path.
    2. Reject filesystem roots (POSIX ``/`` and Windows drive roots).
    3. Reject directories with fewer than ``_PARTS_FLOOR`` path components —
       this blocks ``/etc``, ``/usr``, ``C:\\Windows``, and other near-root
       paths that would be catastrophic to delete.
    4. Allow only the application's ``DEFAULT_SESSION`` (or a strict child
       of it). A name-pattern fallback such as "any directory called
       ``session`` under the home directory" is intentionally dropped — the
       destructive authorisation policy must whitelist exactly one known
       location, not a pattern that could match ``~/projects/session`` or
       ``~/dev/qwen_session``.

    No other path shape is permitted.
    """
    target = target.resolve() if target.is_absolute() else target
    if not target.is_absolute():
        return False
    if is_filesystem_root(target):
        return False
    if len(target.parts) < _PARTS_FLOOR:
        return False
    if not target.is_dir():
        return False

    default_session = DEFAULT_SESSION.resolve()
    return target == default_session or default_session in target.parents


__all__ = ["is_filesystem_root", "is_safe_session_target"]
