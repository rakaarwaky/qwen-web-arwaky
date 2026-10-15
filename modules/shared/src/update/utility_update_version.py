"""Update version helpers (utility layer).

Version parsing and comparison shared by the update capabilities, split
out of ``utility_update_pipeline.py`` so a capability that only compares
versions does not also pull in the subprocess sandbox and the GitHub
client. Pure functions, no I/O.
"""

from __future__ import annotations

import re

from modules.shared.src.common.taxonomy_core_vo import VersionString

__all__ = [
    "compare_versions",
    "version_unresolvable",
]


def _parse_version_tuple(version: str) -> tuple[tuple[int, int, str], ...]:
    """Parse a semver-ish string into a comparable tuple (zero external deps)."""
    cleaned = str(version).strip().lstrip("vV")
    parts: list[tuple[int, int, str]] = []
    for chunk in re.split(r"[.\-+]", cleaned):
        if not chunk:
            continue
        match = re.match(r"^(\d+)(.*)$", chunk)
        if match:
            parts.append((0, int(match.group(1)), match.group(2)))
        else:
            parts.append((1, 0, chunk))
    return tuple(parts)


def compare_versions(left: str, right: str) -> int:
    """Return >0 when *left* is newer than *right*, <0 when older, 0 when equal."""
    left_parts = _parse_version_tuple(left)
    right_parts = _parse_version_tuple(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def version_unresolvable() -> VersionString:
    """Return the canonical 'unknown' version marker used when no version resolves."""
    return VersionString("unknown")
