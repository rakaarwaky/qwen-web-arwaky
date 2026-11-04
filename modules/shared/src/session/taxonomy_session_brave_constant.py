"""Brave session domain constants (taxonomy layer).

Pure constant values for Brave profile discovery. No I/O.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Flatpak data root prefix used to label the source of a discovered profile.
FLATPAK_ROOT = Path(os.path.expanduser("~/.var/app/com.brave.Browser"))

__all__ = ["FLATPAK_ROOT"]
