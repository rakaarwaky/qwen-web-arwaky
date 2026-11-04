"""Brave browser profile path discovery (utility layer).

Scans Flatpak Brave data directories for existing Chromium profiles that
carry auth cookies (``Default/Cookies``) or profile state (``Local State``).
Brave profiles are read-only masters: qwen never writes to them directly.

AES201: utility layer imports taxonomy only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: Brave Flatpak data root candidates. The first existing one wins.
BRAVE_DATA_DIR_CANDIDATES: tuple[str, ...] = (os.path.expanduser("~/.var/app/com.brave.Browser"),)

#: Environment override for the Brave data root.
BRAVE_DATA_DIR_ENV = "QWEN_BRAVE_DATA_DIR"

#: Source labels for discovered profiles.
SOURCE_FLATPAK = "flatpak"
SOURCE_SYSTEM = "system"


def _brave_data_root() -> Path | None:
    """Resolve the Brave data root from env override or Flatpak candidates.

    Best-effort: returns None when no candidate directory exists.
    """
    override = os.environ.get(BRAVE_DATA_DIR_ENV, "").strip()
    if override:
        return Path(override)
    for candidate in BRAVE_DATA_DIR_CANDIDATES:
        path = Path(candidate)
        if path.is_dir():
            return path
    return None


def _is_flatpak_root(root: Path) -> bool:
    """True when *root* lives under the Flatpak user data tree."""
    try:
        root.resolve().relative_to(Path.home() / ".var" / "app" / "com.brave.Browser")
        return True
    except ValueError:
        return False


def _has_profile_marker(profile_dir: Path) -> bool:
    """True when *profile_dir* carries Chromium profile content.

    Recognizes three marker shapes:
    - ``Default/Cookies`` — nested-profile layout (qwen-managed, web-app-hub)
    - ``Local State``     — Chromium user-data root
    - ``Cookies``         — flat-profile layout (regular Brave profiles such
      as arwaky001/prof1 where the cookie jar lives at the profile root)
    """
    return (
        (profile_dir / "Default" / "Cookies").is_file()
        or (profile_dir / "Local State").is_file()
        or (profile_dir / "Cookies").is_file()
    )


def _config_profiles(root: Path) -> list[Path]:
    """Yield profile dirs under config/BraveSoftware/Brave-Browser/*."""
    brave_browser = root / "config" / "BraveSoftware" / "Brave-Browser"
    if not brave_browser.is_dir():
        return []
    profiles: list[Path] = []
    for child in sorted(brave_browser.iterdir()):
        if child.is_symlink() or not child.is_dir():
            continue
        if _has_profile_marker(child):
            profiles.append(child)
    return profiles


def _web_app_hub_profiles(root: Path) -> list[Path]:
    """Yield profile dirs under data/web-app-hub/profiles/*/.

    Web-app-hub layouts place a per-PWA Chromium data dir at
    ``profiles/<hash>/`` whose profile content lives in ``Default/``
    (carrying ``Default/Cookies`` + a root ``Local State``). The actual
    Chromium profile directory the preparer will clone is the ``Default``
    sub-dir when it carries the marker, otherwise the hash dir itself.
    """
    hub = root / "data" / "web-app-hub" / "profiles"
    if not hub.is_dir():
        return []
    profiles: list[Path] = []
    for child in sorted(hub.iterdir()):
        if child.is_symlink() or not child.is_dir():
            continue
        default_dir = child / "Default"
        if _has_profile_marker(default_dir):
            profiles.append(default_dir)
        elif _has_profile_marker(child):
            profiles.append(child)
    return profiles


def find_brave_profiles() -> list[Path]:
    """Return every discovered Brave profile directory.

    Best-effort: missing directories return an empty list. Never raises.
    """
    root = _brave_data_root()
    if root is None:
        return []
    return _config_profiles(root) + _web_app_hub_profiles(root)


def brave_profile_name(profile_dir: Path) -> str:
    """Best-effort profile name from Local State, falling back to dir name.

    Reads the Chromium ``Local State`` profile info block. Falls back to
    ``profile_dir.name`` when the file is absent, unreadable, or lacks a name.
    """
    local_state = profile_dir / "Local State"
    if not local_state.is_file():
        return profile_dir.name
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return profile_dir.name
    if not isinstance(data, dict):
        return profile_dir.name
    profile_block = data.get("profile", {})
    if not isinstance(profile_block, dict):
        return profile_dir.name
    info = profile_block.get("info", {})
    if not isinstance(info, dict):
        return profile_dir.name
    entry = info.get(profile_dir.name)
    if isinstance(entry, dict):
        name = entry.get("name")
        if isinstance(name, str) and name:
            return name
    for _key, value in info.items():
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name:
                return name
    return profile_dir.name


def is_brave_profile_path(path: Path) -> bool:
    """True when *path* is a Brave profile directory (carries a profile marker)."""
    return _has_profile_marker(path)


__all__ = [
    "BRAVE_DATA_DIR_ENV",
    "SOURCE_FLATPAK",
    "SOURCE_SYSTEM",
    "brave_profile_name",
    "find_brave_profiles",
    "is_brave_profile_path",
]
