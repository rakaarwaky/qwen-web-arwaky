"""Playwright browser path resolution utilities.

Utility layer (utility_core_paths): stateless functions for computing the
Playwright browser cache path. Taxonomy imports only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_playwright_browsers_path() -> Path:
    """Return the Playwright browser cache directory for this platform.

    Honours ``PLAYWRIGHT_BROWSERS_PATH`` when set (unless it is ``"0"``),
    then falls back to the platform-conventional cache location.
    """
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        env_path = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
        if env_path != "0":
            return Path(env_path)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache/ms-playwright"


__all__ = ["get_playwright_browsers_path"]
