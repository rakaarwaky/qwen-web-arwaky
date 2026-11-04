"""Brave session value objects (taxonomy layer).

Immutable value contracts for Brave profile discovery. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BraveProfileInfo:
    """Discovered Brave browser profile metadata.

    Brave profiles are read-only masters: qwen never writes directly to
    them. Runs clone them to ephemeral temp dirs instead.
    """

    path: Path
    name: str
    source: str
    is_regular_browser: bool
    is_web_app_hub: bool


__all__ = ["BraveProfileInfo"]
