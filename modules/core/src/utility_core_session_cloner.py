"""Utility layer: Chromium session cloning and ephemeral profile management.

Enables 1-browser-per-job parallel execution with shared login sessions
by creating isolated temporary clones of the master profile directory.

Security (issue #346): clones carry live authentication cookies, so they are
created under ``$XDG_RUNTIME_DIR`` (a tmpfs cleared at logout) whenever it is
available, orphaned clones left behind by a ``SIGKILL`` or power loss are
swept at process start, and :func:`session_age_warning` reports the master
profile age so operators can re-login before IdP expiry.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_CLONE_LOCK = threading.Lock()
STALE_LOCK_PATTERNS = ("SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort")

# Prefix shared by every ephemeral credential clone; also the glob used to
# recognise orphans left behind by crashed processes.
CLONE_DIR_PREFIX = "qwen_worker_session_"
# Orphan sweep: clones untouched for longer than this are removed at startup.
STALE_CLONE_MAX_AGE_SEC = 24 * 60 * 60
# Master-profile age before ``doctor`` recommends re-login (issue #346).
DEFAULT_SESSION_MAX_AGE_DAYS = 30

# Runs at most once per process, when the first clone is requested.
_startup_sweep_lock = threading.Lock()
_startup_sweep_done = False


def clone_base_dir() -> str | None:
    """Return the directory ephemeral credential clones should be created in.

    ``$XDG_RUNTIME_DIR`` is preferred because it is per-user, mode ``0o700``,
    and cleared on logout — so a crashed process cannot leave readable cookies
    behind in a shared ``/tmp``. Returns ``None`` when the variable is unset
    or unusable, which makes ``tempfile`` fall back to the system temp dir.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if not runtime:
        return None
    path = Path(runtime)
    if not path.is_dir() or not os.access(runtime, os.W_OK):
        return None
    return runtime


def sweep_stale_clones(max_age_sec: int = STALE_CLONE_MAX_AGE_SEC) -> list[Path]:
    """Delete orphan credential clones older than *max_age_sec* and return their paths.

    A ``SIGKILL``, power loss, or executor crash bypasses the context-manager
    cleanup, so full credential copies would otherwise linger in the temp
    directory indefinitely. Removal is best-effort: a clone still owned by a
    live process is younger than the threshold and therefore never matched.
    """
    removed: list[Path] = []
    bases = [Path(base) for base in (clone_base_dir(), tempfile.gettempdir()) if base]
    cutoff = time.time() - max_age_sec
    seen: set[Path] = set()
    for base in bases:
        try:
            entries = list(base.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.name.startswith(CLONE_DIR_PREFIX) or not entry.is_dir():
                continue
            try:
                if entry in seen or entry.stat().st_mtime > cutoff:
                    continue
                shutil.rmtree(entry)
            except OSError:
                continue
            seen.add(entry)
            removed.append(entry)
    return removed


def _sweep_once() -> None:
    """Run the orphan sweep at most once per process."""
    global _startup_sweep_done
    with _startup_sweep_lock:
        if _startup_sweep_done:
            return
        _startup_sweep_done = True
    for stale in sweep_stale_clones():
        logging.getLogger("qwen-web.session_cloner").info("stale_session_clone_removed", extra={"path": str(stale)})


def session_profile_age_days(master_session: Path) -> float | None:
    """Return how many days ago the master session profile was last modified.

    Returns ``None`` when the profile does not exist or cannot be stat'ed.
    Used by ``doctor`` to flag stale credentials before they hit an IdP
    expiry.
    """
    try:
        mtime = master_session.stat().st_mtime
    except OSError:
        return None
    return max(0.0, (time.time() - mtime) / 86400.0)


def session_age_warning(master_session: Path, max_age_days: int = DEFAULT_SESSION_MAX_AGE_DAYS) -> str | None:
    """Return a re-login recommendation string when the profile is older than *max_age_days*."""
    age_days = session_profile_age_days(master_session)
    if age_days is None or age_days <= max_age_days:
        return None
    return (
        f"Session profile is {age_days:.1f} days old (threshold: {max_age_days} days). "
        "Cookies may be near IdP expiry — run 'qwen-web-arwaky login' to refresh credentials."
    )


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

    _sweep_once()
    with tempfile.TemporaryDirectory(prefix=CLONE_DIR_PREFIX, dir=clone_base_dir()) as tmp_dir:
        ephemeral_path = Path(tmp_dir)
        with contextlib.suppress(OSError):
            ephemeral_path.chmod(0o700)
        clone_session_profile(master_session, ephemeral_path)
        yield ephemeral_path


__all__ = [
    "CLONE_DIR_PREFIX",
    "DEFAULT_SESSION_MAX_AGE_DAYS",
    "STALE_CLONE_MAX_AGE_SEC",
    "clean_stale_locks",
    "clone_base_dir",
    "clone_session_profile",
    "create_ephemeral_session",
    "session_age_warning",
    "session_profile_age_days",
    "sweep_stale_clones",
]
