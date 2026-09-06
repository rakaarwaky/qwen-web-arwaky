"""Utility layer: Chromium session cloning and ephemeral profile management.

Enables 1-browser-per-job parallel execution with shared login sessions
by creating isolated temporary clones of the master profile directory.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_CLONE_LOCK = threading.Lock()
STALE_LOCK_PATTERNS = ("SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort")


def clean_stale_locks(profile_dir: Path) -> None:
    """Remove Chromium singleton locks and active port files from a profile directory."""
    for fname in STALE_LOCK_PATTERNS:
        lock_path = profile_dir / fname
        with contextlib.suppress(OSError):
            if lock_path.is_symlink() or lock_path.exists():
                lock_path.unlink(missing_ok=True)


def clone_session_profile(src: Path, dst: Path) -> None:
    """Clone master profile files into destination directory, ignoring locks and broken symlinks."""
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists() or not src.is_dir():
        with contextlib.suppress(OSError):
            dst.chmod(0o700)
        return

    with _CLONE_LOCK:
        shutil.copytree(
            src,
            dst,
            ignore=shutil.ignore_patterns("Singleton*", "DevToolsActivePort"),
            ignore_dangling_symlinks=True,
            dirs_exist_ok=True,
        )

    clean_stale_locks(dst)
    with contextlib.suppress(OSError):
        dst.chmod(0o700)
        for sub in dst.rglob("*"):
            if sub.is_dir():
                sub.chmod(0o700)


@contextmanager
def create_ephemeral_session(
    master_session: Path,
    mode: str = "",
) -> Iterator[Path]:
    """Provide an isolated session directory for a browser instance.

    For login mode, yields the master session directly so user credentials
    persist. For standard runs/jobs, clones the master session into an
    ephemeral temporary directory so multiple browser processes can run
    concurrently without Chromium SingletonLock conflicts.
    """
    master_session.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        master_session.chmod(0o700)
    clean_stale_locks(master_session)

    if mode == "login":
        yield master_session
        return

    with tempfile.TemporaryDirectory(prefix="qwen_worker_session_") as tmp_dir:
        ephemeral_path = Path(tmp_dir)
        clone_session_profile(master_session, ephemeral_path)
        yield ephemeral_path


__all__ = [
    "clean_stale_locks",
    "clone_session_profile",
    "create_ephemeral_session",
]
