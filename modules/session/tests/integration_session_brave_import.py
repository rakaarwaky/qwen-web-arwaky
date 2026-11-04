"""Integration tests for Brave profile import into the qwen session pool.

Point SESSIONS_DIR at a tmp tree, create a fake Brave master profile, and
verify:
1. Discovery finds the Brave profile.
2. ``register_brave_profile`` registers it in the pool with status
   ``AUTH_REQUIRED`` and the Brave path as the session path.
3. ProfilePreparer forces an ephemeral clone for Brave masters (never
   exposes the live Brave path as writable).
4. Existing qwen-managed sessions under SESSIONS_DIR still work (no
   regression).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules.session.src.capabilities_session_manager import SessionManager
from modules.session.src.capabilities_session_profile_preparer import ProfilePreparer
from modules.shared.src.session.taxonomy_session_brave_vo import BraveProfileInfo
from modules.shared.src.session.utility_session_brave_paths import (
    is_brave_profile_path,
)

MODULE = "modules.session.src.capabilities_session_manager"
MANAGER_MODULE = "modules.session.src.capabilities_session_manager"


def _make_brave_profile(root: Path, name: str) -> Path:
    """Create a flat-layout Brave master profile (Cookies at profile root)."""
    profile = root / name
    profile.mkdir(parents=True)
    (profile / "Cookies").write_text("cookiejar", encoding="utf-8")
    (profile / "Local State").write_text(
        '{"profile": {"info": {"' + name + '": {"name": "Brave ' + name + '"}}}}',
        encoding="utf-8",
    )
    return profile


def _make_qwen_profile(root: Path, name: str) -> Path:
    """Create a qwen-managed profile (Default/Cookies nested layout)."""
    profile = root / name
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("cookiejar", encoding="utf-8")
    (profile / "Local State").write_text("{}", encoding="utf-8")
    return profile


def _patched_manager(tmp_path: Path) -> SessionManager:
    """Build a SessionManager rooted at *tmp_path* with patched module globals."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MODULE}.POOL_FILE", pool_file),
    ):
        return SessionManager(base_dir=sessions_dir)


def test_register_brave_profile_auth_required(tmp_path: Path) -> None:
    """Registering a Brave profile stores the master path with AUTH_REQUIRED."""
    brave_root = tmp_path / "brave"
    brave_profile = _make_brave_profile(brave_root, "arwaky001")

    info = BraveProfileInfo(
        path=brave_profile.resolve(),
        name="Brave arwaky001",
        source="flatpak",
        is_regular_browser=True,
        is_web_app_hub=False,
    )

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MANAGER_MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MANAGER_MODULE}.POOL_FILE", pool_file),
    ):
        manager = SessionManager(base_dir=sessions_dir)
        registered = manager.register_brave_profile(info)
        pool = manager.load_pool()

    assert registered.path == brave_profile.resolve()
    assert registered.name == "Brave arwaky001"
    assert registered.is_auth_required
    # Pool persistence.
    assert pool.total_count == 1
    assert pool.sessions[0].path == brave_profile.resolve()
    assert pool.sessions[0].is_auth_required


def test_register_brave_profile_idempotent_updates_name(tmp_path: Path) -> None:
    """Re-registering the same Brave path updates only the name."""
    brave_root = tmp_path / "brave"
    brave_profile = _make_brave_profile(brave_root, "arwaky001")

    info = BraveProfileInfo(
        path=brave_profile.resolve(),
        name="First Name",
        source="flatpak",
        is_regular_browser=True,
        is_web_app_hub=False,
    )
    info2 = BraveProfileInfo(
        path=brave_profile.resolve(),
        name="Second Name",
        source="flatpak",
        is_regular_browser=True,
        is_web_app_hub=False,
    )

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MANAGER_MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MANAGER_MODULE}.POOL_FILE", pool_file),
    ):
        manager = SessionManager(base_dir=sessions_dir)
        first = manager.register_brave_profile(info)
        second = manager.register_brave_profile(info2)
        pool = manager.load_pool()

    assert first.path == second.path
    assert second.name == "Second Name"
    assert pool.total_count == 1  # no duplicate row


def test_profile_preparer_clones_brave_master_even_in_login_mode(tmp_path: Path) -> None:
    """For a Brave master, prepare() yields an ephemeral clone, not the live path."""
    brave_root = tmp_path / "brave"
    brave_profile = _make_brave_profile(brave_root, "arwaky001")

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MANAGER_MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MANAGER_MODULE}.POOL_FILE", pool_file),
    ):
        manager = SessionManager(base_dir=sessions_dir)
        manager.register_brave_profile(
            BraveProfileInfo(
                path=brave_profile.resolve(),
                name="Brave arwaky001",
                source="flatpak",
                is_regular_browser=True,
                is_web_app_hub=False,
            )
        )

    preparer = ProfilePreparer()
    from modules.shared.src.common.taxonomy_core_vo import AppConfig

    cfg = AppConfig(
        mode="login",
        input_path=str(tmp_path / "in.md"),
        output_path=str(tmp_path / "out.md"),
        session_path=brave_profile.resolve(),
        headless=True,
    )

    with preparer.prepare(cfg) as prepared:
        # The prepared path must NOT be the live Brave master path.
        assert prepared != brave_profile.resolve()
        assert prepared.is_dir()
        # The clone carries Chromium content.
        assert (prepared / "Cookies").exists() or (prepared / "Default" / "Cookies").exists()


def test_qwen_managed_session_still_works(tmp_path: Path) -> None:
    """No regression: a qwen-managed profile under SESSIONS_DIR is still registered."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    _make_qwen_profile(sessions_dir, "default")

    with (
        patch(f"{MANAGER_MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MANAGER_MODULE}.POOL_FILE", pool_file),
    ):
        manager = SessionManager(base_dir=sessions_dir)
        pool = manager.load_pool()

    names = {s.name for s in pool.sessions}
    assert "default" in names
    assert pool.sessions[0].is_auth_required


def test_is_brave_profile_path_true_for_brave_master() -> None:
    """is_brave_profile_path True for a profile with root-level Cookies."""
    profile = Path("/tmp/brave-check-profile")
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "Cookies").write_text("c", encoding="utf-8")
    try:
        assert is_brave_profile_path(profile) is True
    finally:
        import shutil

        shutil.rmtree(profile, ignore_errors=True)
