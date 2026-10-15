"""Update Chromium cache helpers (utility layer).

Playwright browser-cache resolution and cache purging, split out of
``utility_update_pipeline.py``. The cache path honours
``PLAYWRIGHT_BROWSERS_PATH`` and otherwise falls back to the per-platform
default, so capabilities that only check or clear the cache do not also
pull in the subprocess sandbox or the GitHub client.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

__all__ = [
    "playwright_browsers_path",
    "chromium_present",
    "purge_chromium_cache",
]

log = logging.getLogger("utility_update_chromium")


def playwright_browsers_path() -> Path:
    """Resolve the Playwright browser cache honoring PLAYWRIGHT_BROWSERS_PATH."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env != "0":
        return Path(env)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def chromium_present() -> bool:
    """True when a Playwright-cached Chromium build or a system Chromium exists."""
    browsers = playwright_browsers_path()
    if browsers.is_dir() and any(browsers.glob("chromium-*")):
        return True
    return any(shutil.which(name) for name in ("chromium", "chromium-browser", "chrome", "google-chrome"))


def purge_chromium_cache() -> int:
    """Delete cached ``chromium-*`` build directories. Returns the count purged."""
    browsers = playwright_browsers_path()
    if not browsers.is_dir():
        return 0
    purged = 0
    for entry in browsers.iterdir():
        if entry.is_dir() and entry.name.startswith("chromium-"):
            try:
                shutil.rmtree(entry)
                purged += 1
            except OSError as exc:
                log.warning("chromium_cache_purge_failed path=%s error=%s", entry, exc)
    return purged
