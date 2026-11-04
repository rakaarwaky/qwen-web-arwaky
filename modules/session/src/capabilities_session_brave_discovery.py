"""Brave profile discovery capability (capabilities layer).

Discovers existing Brave browser profiles on the host and maps them to
:class:`BraveProfileInfo` value objects. Never raises: missing directories
yield an empty list.

AES201: capability layer imports contracts, taxonomy, and utilities only.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.session.contract_session_protocol import ISessionBraveDiscoveryProtocol
from modules.shared.src.session.taxonomy_session_brave_constant import FLATPAK_ROOT
from modules.shared.src.session.taxonomy_session_brave_vo import BraveProfileInfo
from modules.shared.src.session.utility_session_brave_paths import (
    SOURCE_FLATPAK,
    SOURCE_SYSTEM,
    brave_profile_name,
    find_brave_profiles,
)

# Block 1: Class Definition & Constructor


class SessionBraveDiscovery(ISessionBraveDiscoveryProtocol):
    """Discovers existing Brave profiles and registers them as candidate sessions."""

    # Block 2: Protocol Method Implementation

    def discover(self) -> list[BraveProfileInfo]:
        """Return every discoverable Brave profile as :class:`BraveProfileInfo`.

        Best-effort: missing directories return an empty list. Never raises.
        """
        profiles: list[BraveProfileInfo] = []
        for profile_dir in find_brave_profiles():
            resolved = profile_dir.resolve()
            is_flatpak = _is_under(resolved, FLATPAK_ROOT)
            source = SOURCE_FLATPAK if is_flatpak else SOURCE_SYSTEM
            is_web_app_hub = any(part == "web-app-hub" for part in resolved.parts)
            profiles.append(
                BraveProfileInfo(
                    path=resolved,
                    name=brave_profile_name(profile_dir),
                    source=source,
                    is_regular_browser=not is_web_app_hub,
                    is_web_app_hub=is_web_app_hub,
                )
            )
        return profiles


# Block 3: Dunder Methods, Factories & Helpers


def _is_under(path: Path, root: Path) -> bool:
    """True when *path* is *root* or lives beneath it."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


__all__ = ["SessionBraveDiscovery"]
