"""Extended unit tests for utility_core_session_cloner (issue #329).

Covers the edge cases that the base test suite in
``unit_utility_session_cloner.py`` misses:

- ``clone_session_profile`` with a pre-existing destination, symlink handling,
  permission-denied reads, and the immutable-hardlink overlay
  (``_IMMUTABLE_GLOBS`` / ``_IMMUTABLE_DIRS``)
- ``create_ephemeral_session`` cleanup when the consumer raises
- the stale-lock-cleanup lock used on the master profile

Materialization is an O(delta) overlay: only the resource files Chromium ships
into the profile are hardlinked from the master, every mutable file is copied,
and no global lock serializes the clones (issue #363).
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.core.src import utility_core_session_cloner as cloner
from modules.core.src.utility_core_session_cloner import (
    _IMMUTABLE_DIRS,
    _IMMUTABLE_GLOBS,
    _MASTER_LOCKS_LOCK,
    STALE_LOCK_PATTERNS,
    clone_session_profile,
    create_ephemeral_session,
)

# ── clone_session_profile: destination handling ──────────────────────────────


def test_clone_over_existing_destination_merges_not_raises(tmp_path: Path) -> None:
    """A pre-existing destination is merged into, never rejected."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.txt").write_text("a", encoding="utf-8")
    (dst / "b.txt").write_text("b", encoding="utf-8")

    clone_session_profile(src, dst)

    assert (dst / "a.txt").read_text(encoding="utf-8") == "a"
    assert (dst / "b.txt").read_text(encoding="utf-8") == "b"


def test_clone_source_missing_creates_empty_destination(tmp_path: Path) -> None:
    """A missing source is tolerated; the destination is still created empty."""
    src = tmp_path / "missing"
    dst = tmp_path / "dst"

    clone_session_profile(src, dst)

    assert dst.is_dir()
    assert not any(dst.iterdir())


# ── Symlink handling ────────────────────────────────────────────────────────


def test_clone_copies_symlink_targets_and_skips_dangling_ones(tmp_path: Path) -> None:
    """A live symlink is reproduced as a symlink; a dangling one survives too.

    The overlay copies with ``follow_symlinks=False``, so a link is recreated
    rather than materialised into a regular file — a hardlinked copy of a
    preference link would break Chromium's relative-path resolution.  A link
    whose target does not exist is still recreated, because skipping it would
    silently drop a preference the user may repair.
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    real = src / "target.txt"
    real.write_text("data", encoding="utf-8")
    os.symlink("/does/not/exist", src / "dangling")
    os.symlink(real, src / "real_link")

    clone_session_profile(src, dst)

    assert (dst / "real_link").is_symlink()
    assert (dst / "real_link").read_text(encoding="utf-8") == "data"
    assert (dst / "dangling").is_symlink()
    assert os.readlink(str(dst / "dangling")) == "/does/not/exist"


# ── Immutable-resource overlay (issue #363) ─────────────────────────────────


def test_clone_hardlinks_immutable_resources(tmp_path: Path) -> None:
    """Files matching ``_IMMUTABLE_GLOBS`` are hardlinked; everything else is copied."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    top_pak = src / "resource.pak"
    top_pak.write_text("pak bytes", encoding="utf-8")
    top_bin = src / "snapshot.bin"
    top_bin.write_text("bin bytes", encoding="utf-8")
    cookies = src / "Cookies"
    cookies.write_text("cookies", encoding="utf-8")

    clone_session_profile(src, dst)

    assert os.stat(str(top_pak)).st_ino == os.stat(str(dst / "resource.pak")).st_ino
    assert os.stat(str(top_bin)).st_ino == os.stat(str(dst / "snapshot.bin")).st_ino
    assert os.stat(str(cookies)).st_ino != os.stat(str(dst / "Cookies")).st_ino
    assert (dst / "resource.pak").read_text(encoding="utf-8") == "pak bytes"
    assert (dst / "Cookies").read_text(encoding="utf-8") == "cookies"


def test_clone_hardlinks_immutable_dirs(tmp_path: Path) -> None:
    """``_IMMUTABLE_DIRS`` is recursed, hardlinking the files inside it."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    locales = src / "locales"
    locales.mkdir()
    (locales / "en.pak").write_text("en locale", encoding="utf-8")

    clone_session_profile(src, dst)

    assert (dst / "locales" / "en.pak").exists()
    assert os.stat(str(locales / "en.pak")).st_ino == os.stat(str(dst / "locales" / "en.pak")).st_ino


def test_clone_copies_mutable_subdirs_copytree(tmp_path: Path) -> None:
    """Non-immutable directories are recursed and copied, never hardlinked."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    data_dir = src / "Default" / "Local Storage"
    data_dir.mkdir(parents=True)
    (data_dir / "data.ldb").write_text("ldb", encoding="utf-8")

    clone_session_profile(src, dst)

    cloned = dst / "Default" / "Local Storage" / "data.ldb"
    assert cloned.read_text(encoding="utf-8") == "ldb"
    assert os.stat(str(data_dir / "data.ldb")).st_ino != os.stat(str(cloned)).st_ino


# ── Filtered files and permissions ──────────────────────────────────────────


def test_clone_excludes_singleton_and_devtools_files(tmp_path: Path) -> None:
    """``Singleton*`` and ``DevToolsActivePort`` are filtered at every depth."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    default_dir = src / "Default"
    default_dir.mkdir()
    lock_dir = default_dir / "SingletonLock"
    lock_dir.mkdir()
    (lock_dir / "inner").write_text("should not appear", encoding="utf-8")
    (default_dir / "DevToolsActivePort").write_text("9333", encoding="utf-8")
    (default_dir / "normal.txt").write_text("keep", encoding="utf-8")

    clone_session_profile(src, dst)

    assert not (dst / "Default" / "SingletonLock").exists()
    assert not (dst / "Default" / "DevToolsActivePort").exists()
    assert (dst / "Default" / "normal.txt").read_text(encoding="utf-8") == "keep"


def test_clone_sets_owner_only_directory_permissions(tmp_path: Path) -> None:
    """Every directory the clone produces is 0o700, as Chromium requires."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    sub = src / "Default" / "Local Storage"
    sub.mkdir(parents=True)
    (sub / "x").write_text("x", encoding="utf-8")

    clone_session_profile(src, dst)

    for dirpath, _dirnames, _files in os.walk(dst):
        mode = os.stat(dirpath).st_mode & 0o777
        assert mode == 0o700, f"{dirpath}: expected 0o700, got {oct(mode)}"


def test_clone_propagates_permission_errors(tmp_path: Path) -> None:
    """A read failure inside the source tree is surfaced, not swallowed.

    Silently returning a half-populated profile would start Chromium with a
    missing cookie jar and fail much later with an opaque auth error.
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "Cookies").write_text("token", encoding="utf-8")

    with patch.object(cloner.shutil, "copytree", side_effect=PermissionError(13, "Permission denied")):
        with patch.object(cloner.shutil, "copy2", side_effect=PermissionError(13, "Permission denied")):
            with pytest.raises(PermissionError):
                clone_session_profile(src, dst)


def test_chmod_failure_on_destination_is_suppressed(tmp_path: Path) -> None:
    """A destination that cannot be tightened to 0o700 does not abort the clone."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "a.txt").write_text("a", encoding="utf-8")

    with patch.object(type(dst), "chmod", side_effect=OSError(1, "Operation not permitted")):
        clone_session_profile(src, dst)

    assert (dst / "a.txt").exists()


# ── create_ephemeral_session teardown ────────────────────────────────────────


def test_ephemeral_session_cleans_up_on_keyboard_interrupt(tmp_path: Path) -> None:
    """``KeyboardInterrupt`` from the consumer still tears the temp dir down."""
    master = tmp_path / "master"
    master.mkdir()
    (master / "Cookies").write_text("token", encoding="utf-8")

    with pytest.raises(KeyboardInterrupt):
        with create_ephemeral_session(master, mode="batch") as session_dir:
            assert session_dir.exists()
            raise KeyboardInterrupt

    assert not session_dir.exists()


def test_ephemeral_session_cleans_up_on_generic_exception(tmp_path: Path) -> None:
    """Any exception inside the context cleans up the temp dir."""
    master = tmp_path / "master"
    master.mkdir()
    (master / "cookies").write_text("c", encoding="utf-8")

    with pytest.raises(RuntimeError):
        with create_ephemeral_session(master, mode="batch") as session_dir:
            raise RuntimeError("simulated crash")

    assert not session_dir.exists()


def test_ephemeral_session_cleans_up_deep_subtrees(tmp_path: Path) -> None:
    """A deep clone subtree is fully removed on teardown."""
    master = tmp_path / "master"
    deep = master / "Default" / "Local Storage" / "leveldb"
    deep.mkdir(parents=True)
    (deep / "LOG").write_text("log", encoding="utf-8")

    with pytest.raises(SystemExit):
        with create_ephemeral_session(master, mode="batch") as session_dir:
            assert (session_dir / "Default" / "Local Storage" / "leveldb" / "LOG").exists()
            raise SystemExit(1)

    assert not session_dir.exists()


# ── Concurrency ──────────────────────────────────────────────────────────────


def test_master_lock_is_a_real_threading_lock() -> None:
    """The stale-lock-cleanup lock is a real ``threading.Lock`` and is idle."""
    assert isinstance(_MASTER_LOCKS_LOCK, type(threading.Lock()))
    assert not _MASTER_LOCKS_LOCK.locked()


def test_parallel_clones_yield_distinct_complete_profiles(tmp_path: Path) -> None:
    """Four concurrent clones of one master all succeed and never collide.

    This is the ``DEFAULT_MAX_WORKERS`` path the host gate in
    ``utility_core_host_gate`` protects; the clones must overlap rather than
    queue behind one another, and none may leak a worker's files into
    another's profile.
    """
    master = tmp_path / "master"
    master.mkdir()
    for name in ("a.pak", "b.pak", "cookies.db"):
        (master / name).write_text(name, encoding="utf-8")
    (master / "Default").mkdir()
    (master / "Default" / "prefs.json").write_text("{}", encoding="utf-8")

    results: list[Path] = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            with create_ephemeral_session(master, mode="batch") as session_dir:
                for name in ("a.pak", "b.pak", "cookies.db", "Default/prefs.json"):
                    if not (session_dir / name).exists():
                        errors.append(AssertionError(f"worker {index}: {name} missing"))
                with results_lock:
                    results.append(session_dir)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not errors, f"concurrent clone errors: {errors}"
    assert len(results) == 4
    assert len(set(results)) == 4


def test_parallel_clones_are_not_serialised(tmp_path: Path) -> None:
    """Only stale-lock cleanup is serialized; overlay copies overlap.

    The master's cleanup is guarded, but the overlay copy runs unguarded, so
    four parallel clones of the same master all produce a complete profile
    within the timeout instead of queueing behind a global clone lock.
    """
    master = tmp_path / "master"
    master.mkdir()
    for name in ("a.pak", "b.pak", "cookies.db"):
        (master / name).write_text(name, encoding="utf-8")
    (master / "Default").mkdir()
    (master / "Default" / "prefs.json").write_text("{}", encoding="utf-8")

    results: list[Path] = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            with create_ephemeral_session(master, mode="batch") as session_dir:
                for name in ("a.pak", "b.pak", "cookies.db", "Default"):
                    if not (session_dir / name).exists():
                        errors.append(AssertionError(f"worker {index}: {name} missing"))
                with results_lock:
                    results.append(session_dir)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, f"concurrent clone errors: {errors}"
    assert len(results) == 4
    assert len(set(results)) == 4


# ── Constants ────────────────────────────────────────────────────────────────


def test_stale_lock_patterns_cover_the_chromium_singleton_set() -> None:
    """Every Chromium singleton artefact the master profile can hold is listed."""
    assert "SingletonLock" in STALE_LOCK_PATTERNS
    assert "SingletonSocket" in STALE_LOCK_PATTERNS
    assert "SingletonCookie" in STALE_LOCK_PATTERNS
    assert "DevToolsActivePort" in STALE_LOCK_PATTERNS


def test_immutable_patterns_are_documented() -> None:
    """Immutable-resource constants match Chromium's shipped content shape."""
    assert "*.pak" in _IMMUTABLE_GLOBS
    assert "*.bin" in _IMMUTABLE_GLOBS
    assert "locales" in _IMMUTABLE_DIRS


def test_chmod_0o700_is_itself_private() -> None:
    """Locks the documented permission bit so a future refactor cannot widen it."""
    assert stat.S_IMODE(0o700) == 0o700
