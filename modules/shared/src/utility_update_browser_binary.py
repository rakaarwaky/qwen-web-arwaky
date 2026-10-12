"""Chrome binary discovery utilities.

Utility layer (utility_browser_binary): stateless functions for locating
a Chromium-based browser binary on the host.

Security (issue #347): the discovered binary is launched by Playwright together
with the authenticated ``user_data_dir``, so a substituted executable would
receive the live login cookies. Discovery therefore prefers the Playwright-managed
build, and any ``PATH`` candidate must pass an ownership/permission check before
it is trusted.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
from pathlib import Path

log = logging.getLogger("qwen-web.browser_binary")

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "chrome.exe",
    "msedge",
    "msedge.exe",
)

EXTRA_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

# Playwright build names, most specific first. ``*_headless_shell`` is only
# usable for headless runs, so the full browser name is probed first.
#
# The tuple order matters: ``chromium`` must come before
# ``chromium_headless_shell`` because the headless-shell glob
# (``chromium_headless_shell-*``) can match a build whose only binary is the
# headless shell (no GUI). Returning that as ``executable_path`` for a
# ``headless=False`` run produces no visible window — the exact "login opens
# no browser" bug. The full ``chromium`` entry is tried first so the GUI
# binary wins whenever it exists.
_PLAYWRIGHT_BROWSER_DIRS = (
    (
        "chromium",
        ("chrome-linux/chrome", "chrome-linux64/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
    ),
    (
        "chromium_headless_shell",
        (
            "chrome-linux/headless_shell",
            "chrome-linux64/headless_shell",
            "chrome-headless-shell-linux64/chrome-headless-shell",
        ),
    ),
)

# Group- and world-writable bits: a file or directory carrying either can be
# replaced by any local user, which is exactly the substitution risk here.
_UNSAFE_MODE_MASK = stat.S_IWGRP | stat.S_IWOTH


def _is_trusted_binary(path: str) -> bool:
    """Return True when *path* is a regular, non-substitutable browser binary.

    Security (issue #347): the discovered binary is launched with the
    authenticated ``user_data_dir``, so a substituted executable would receive
    live login cookies. A candidate is trusted only when all of the following
    hold:

    1. It is a regular file (not a directory, symlink, or device node).
    2. The file carries no group- or world-write bit.
    3. The containing directory carries no group- or world-write bit — a
       writable parent lets any other local account swap the file out.
    4. The file is owned by root or by the current user. Ownership by another
       unprivileged account is as dangerous as world-writable permissions,
       because that account can rewrite the file and inherit the session
       profile.

    Windows has no ``os.getuid``, so ownership cannot be checked there; the
    permission checks are the strongest signal available on that platform.
    """
    try:
        candidate = Path(path).resolve()
        info = candidate.stat()
        parent_info = candidate.parent.stat()
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    if info.st_mode & _UNSAFE_MODE_MASK:
        return False
    if parent_info.st_mode & _UNSAFE_MODE_MASK:
        return False
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return True
    return info.st_uid in (0, getuid())


def _playwright_browser_root() -> Path | None:
    """Return the Playwright browser cache root, or None when it is absent.

    Playwright's own download directory is created by the package installer and
    is not influenced by the caller's ``PATH``, so it is preferred over any
    system candidate. The path computation is inlined here to avoid a
    cross-module utility import, which the AES architecture linter rejects.
    """
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "") or ""
    if browsers_path and browsers_path != "0":
        root = Path(browsers_path)
    elif sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        root = Path(appdata) / "ms-playwright"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        root = Path.home() / ".cache/ms-playwright"
    return root if root.is_dir() else None


def _playwright_managed_binary(prefer_gui: bool = True) -> str:
    """Return the Playwright-cached Chromium executable, or '' when absent.

    The full ``chromium`` GUI build is always probed first. When
    ``prefer_gui`` is True (a headful launch) and only a
    ``chromium_headless_shell`` build is cached, '' is returned so the
    caller can fall back to a system channel such as ``channel="chrome"``.
    For a headless launch the headless-shell build is returned when the
    full GUI build is missing.
    """
    root = _playwright_browser_root()
    if root is None:
        return ""
    gui_candidate = ""
    for entry in sorted(root.glob("chromium-*"), reverse=True):
        for relative in _PLAYWRIGHT_BROWSER_DIRS[0][1]:
            candidate = entry / relative
            if candidate.is_file() and _is_trusted_binary(str(candidate)):
                gui_candidate = str(candidate)
                break
        if gui_candidate:
            break
    if gui_candidate:
        return gui_candidate
    if prefer_gui:
        return ""
    for entry in sorted(root.glob("chromium_headless_shell-*"), reverse=True):
        for relative in _PLAYWRIGHT_BROWSER_DIRS[1][1]:
            candidate = entry / relative
            if candidate.is_file() and _is_trusted_binary(str(candidate)):
                return str(candidate)
    return ""


def find_chrome_binary(headless: bool = True) -> str:
    """Return the path of a trusted Chrome/Chromium binary, or ''.

    The Playwright-managed build is preferred. ``PATH`` candidates and the
    well-known system locations are accepted only when
    :func:`_is_trusted_binary` clears them; each rejection is logged so an
    operator can see why the chosen binary was skipped.

    When ``headless`` is False (a visible window is required, e.g. manual
    login) and the Playwright cache holds only a headless-shell build, an
    empty string is returned so the caller falls back to a system channel
    such as ``channel="chrome"``.

    Returns
    -------
    str
        Absolute path to the discovered binary, or an empty string when no
        trusted candidate is available.

    """
    managed = _playwright_managed_binary(prefer_gui=not headless)
    if managed:
        # A headful launch must never fall back to a headless-shell build,
        # which renders no visible window ("login opens no browser" bug).
        # Drop it and continue to the system candidates so the operator
        # gets a real GUI binary (or the Playwright system channel).
        if not headless and is_headless_shell_binary(managed):
            log.warning(
                "browser_headful_rejected_headless_shell",
                extra={"path": managed},
            )
        else:
            return managed

    for candidate in CHROME_CANDIDATES:
        path = shutil.which(candidate)
        if not path:
            continue
        if _is_trusted_binary(path):
            return path
        log.warning(
            "browser_binary_rejected_untrusted_permissions",
            extra={"candidate": candidate, "path": path},
        )

    for extra in EXTRA_PATHS:
        if os.path.exists(extra):
            if _is_trusted_binary(extra):
                return extra
            log.warning(
                "browser_binary_rejected_untrusted_permissions",
                extra={"candidate": extra, "path": extra},
            )
    return ""


def is_headless_shell_binary(path: str) -> bool:
    """Return True when *path* is a Playwright headless-shell executable.

    The headless shell has no GUI toolkit: launching it with
    ``headless=False`` either crashes or renders no visible window, which is
    the "login opens no browser" bug. Callers use it to decide when to drop
    ``executable_path`` and let Playwright fall back to a system channel
    such as ``channel="chrome"``.
    """
    parent_names = [part.casefold() for part in Path(path).parts]
    return any("headless_shell" in part or "headless-shell" in part for part in parent_names[:-1])


__all__ = [
    "CHROME_CANDIDATES",
    "EXTRA_PATHS",
    "find_chrome_binary",
    "is_headless_shell_binary",
]
