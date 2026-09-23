"""Unit tests for utility_core_session_cloner (Method A)."""

from __future__ import annotations

import os
from pathlib import Path

from modules.core.src.utility_core_session_cloner import (
    clean_stale_locks,
    clone_session_profile,
    create_ephemeral_session,
)


def test_clean_stale_locks_removes_singleton_files_and_symlinks(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "file1.txt").write_text("ok", encoding="utf-8")
    (profile / "DevToolsActivePort").write_text("9222", encoding="utf-8")

    # Create dangling symlinks
    os.symlink("fake-host-pid", str(profile / "SingletonLock"))
    os.symlink("fake-host-pid", str(profile / "SingletonSocket"))
    os.symlink("fake-host-pid", str(profile / "SingletonCookie"))

    clean_stale_locks(profile)

    assert (profile / "file1.txt").exists()
    assert not (profile / "DevToolsActivePort").exists()
    assert not (profile / "SingletonLock").exists()
    assert not (profile / "SingletonSocket").exists()
    assert not (profile / "SingletonCookie").exists()


def test_clone_session_profile_handles_nonexistent_src(tmp_path: Path) -> None:
    src = tmp_path / "nonexistent"
    dst = tmp_path / "dst"
    clone_session_profile(src, dst)
    assert dst.exists()
    assert dst.is_dir()


def test_clone_session_profile_clones_data_and_ignores_locks(tmp_path: Path) -> None:
    src = tmp_path / "master"
    src.mkdir()
    (src / "Cookies").write_text("secret_cookie_token", encoding="utf-8")
    sub = src / "Default" / "Local Storage"
    sub.mkdir(parents=True)
    (sub / "data.ldb").write_text("local_storage_val", encoding="utf-8")

    # Create lock symlinks that should be ignored
    os.symlink("fake-host-pid", str(src / "SingletonLock"))
    (src / "DevToolsActivePort").write_text("9333", encoding="utf-8")

    dst = tmp_path / "ephemeral"
    clone_session_profile(src, dst)

    assert (dst / "Cookies").read_text(encoding="utf-8") == "secret_cookie_token"
    assert (dst / "Default" / "Local Storage" / "data.ldb").read_text(encoding="utf-8") == "local_storage_val"
    assert not (dst / "SingletonLock").exists()
    assert not (dst / "DevToolsActivePort").exists()


def test_create_ephemeral_session_login_mode_yields_master(tmp_path: Path) -> None:
    master = tmp_path / "master_session"
    with create_ephemeral_session(master, mode="login") as session_dir:
        assert session_dir == master
        assert session_dir.exists()


def test_create_ephemeral_session_standard_mode_clones_and_cleans_up(tmp_path: Path) -> None:
    master = tmp_path / "master_session"
    master.mkdir()
    (master / "token.txt").write_text("auth_token_123", encoding="utf-8")

    ephemeral_target = None
    with create_ephemeral_session(master, mode="prompt-only") as session_dir:
        ephemeral_target = session_dir
        assert session_dir != master
        assert session_dir.exists()
        assert (session_dir / "token.txt").read_text(encoding="utf-8") == "auth_token_123"

    # Temporary directory must be deleted after exiting context
    assert ephemeral_target is not None
    assert not ephemeral_target.exists()


def test_create_ephemeral_session_parallel_yields_distinct_directories(tmp_path: Path) -> None:
    master = tmp_path / "master_session"
    master.mkdir()
    (master / "Cookies").write_text("shared_login", encoding="utf-8")

    with create_ephemeral_session(master) as s1:
        with create_ephemeral_session(master) as s2:
            assert s1 != s2
            assert s1.exists()
            assert s2.exists()
            assert (s1 / "Cookies").read_text(encoding="utf-8") == "shared_login"
            assert (s2 / "Cookies").read_text(encoding="utf-8") == "shared_login"
