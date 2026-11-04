"""Unit tests for Brave profile discovery (capabilities layer).

Discovery is best-effort: missing Brave dirs yield an empty list and never
raise. Tests mock the filesystem so no real Brave installation is needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from modules.session.src.capabilities_session_brave_discovery import SessionBraveDiscovery
from modules.shared.src.session.taxonomy_session_brave_vo import BraveProfileInfo
from modules.shared.src.session.utility_session_brave_paths import (
    SOURCE_FLATPAK,
    brave_profile_name,
    find_brave_profiles,
    is_brave_profile_path,
)

MODULE = "modules.session.src.capabilities_session_brave_discovery"
UTILS = "modules.shared.src.session.utility_session_brave_paths"


def _make_profile(root: Path, name: str, *, local_state_name: str | None = None) -> Path:
    """Create a Brave-shaped profile directory under *root* with Cookies."""
    profile = root / name
    profile.mkdir(parents=True)
    (profile / "Cookies").write_text("cookiejar", encoding="utf-8")
    local_state = profile / "Local State"
    if local_state_name is not None:
        local_state.write_text(
            '{"profile": {"info": {"' + name + '": {"name": "' + local_state_name + '"}}}}',
            encoding="utf-8",
        )
    else:
        local_state.write_text("{}", encoding="utf-8")
    return profile


@pytest.fixture()
def flatpak_root(tmp_path: Path) -> Path:
    """A fake Flatpak Brave root with config/BraveSoftware/Brave-Browser/<profile>."""
    root = tmp_path / ".var" / "app" / "com.brave.Browser"
    browser = root / "config" / "BraveSoftware" / "Brave-Browser"
    browser.mkdir(parents=True)
    _make_profile(browser, "arwaky001", local_state_name="Arwaky One")
    _make_profile(browser, "prof1")
    _make_profile(browser, "arwaky90", local_state_name="Arwaky 90")
    # Non-profile dir: no Cookies, no Local State — must be skipped.
    (browser / "BrowserMetrics").mkdir()
    return root


@pytest.fixture()
def web_app_hub_root(tmp_path: Path) -> Path:
    """A fake Flatpak Brave root with data/web-app-hub/profiles/<hash>/."""
    root = tmp_path / ".var" / "app" / "com.brave.Browser"
    hub = root / "data" / "web-app-hub" / "profiles"
    hub.mkdir(parents=True)
    pwa = hub / "kzMOyM2h"
    pwa.mkdir(parents=True)
    _make_profile(pwa, "Default", local_state_name="Qwen Web App")
    return root


def _discover_with_root(root: Path | None) -> list[BraveProfileInfo]:
    """Build a discovery instance rooted at *root* and run discover()."""
    discovery = SessionBraveDiscovery()
    flatpak_root = root if root is not None else Path("/tmp/no-brave")
    with (
        patch(f"{UTILS}._brave_data_root", return_value=root),
        patch(f"{MODULE}._FLATPAK_ROOT", flatpak_root),
    ):
        return discovery.discover()


def test_discover_empty_when_no_brave_dirs() -> None:
    """No Brave root → empty list, never raises."""
    profiles = _discover_with_root(None)
    assert profiles == []


def test_discover_flatpak_regular_profiles(flatpak_root: Path) -> None:
    """Regular Flatpak profiles are discovered with source=flatpak."""
    profiles = _discover_with_root(flatpak_root)
    names = {p.name for p in profiles}
    assert names == {"Arwaky One", "prof1", "Arwaky 90"}
    for p in profiles:
        assert p.source == SOURCE_FLATPAK
        assert p.is_regular_browser is True
        assert p.is_web_app_hub is False


def test_discover_web_app_hub_profiles(web_app_hub_root: Path) -> None:
    """Web-app-hub PWA profiles are discovered with is_web_app_hub=True."""
    profiles = _discover_with_root(web_app_hub_root)
    assert len(profiles) == 1
    p = profiles[0]
    assert p.name == "Qwen Web App"
    assert p.source == SOURCE_FLATPAK
    assert p.is_regular_browser is False
    assert p.is_web_app_hub is True


def test_brave_profile_name_falls_back_to_dir_name(tmp_path: Path) -> None:
    """When Local State lacks a name, fall back to the directory name."""
    profile = tmp_path / "arwaky007"
    profile.mkdir()
    (profile / "Cookies").write_text("c", encoding="utf-8")
    # Local State without a name entry.
    (profile / "Local State").write_text('{"profile": {"info": {"arwaky007": {}}}}', encoding="utf-8")
    assert brave_profile_name(profile) == "arwaky007"


def test_is_brave_profile_path_accepts_root_cookies(tmp_path: Path) -> None:
    """is_brave_profile_path True for a profile with root-level Cookies."""
    profile = tmp_path / "brave-prof"
    profile.mkdir()
    (profile / "Cookies").write_text("c", encoding="utf-8")
    assert is_brave_profile_path(profile) is True


def test_find_brave_profiles_returns_empty_when_missing() -> None:
    """find_brave_profiles returns [] when no Brave data root exists."""
    with patch(f"{UTILS}._brave_data_root", return_value=None):
        assert find_brave_profiles() == []


def test_discovery_implements_protocol() -> None:
    """SessionBraveDiscovery satisfies ISessionBraveDiscoveryProtocol."""
    from modules.shared.src.session.contract_session_protocol import (
        ISessionBraveDiscoveryProtocol,
    )

    assert isinstance(SessionBraveDiscovery(), ISessionBraveDiscoveryProtocol)
