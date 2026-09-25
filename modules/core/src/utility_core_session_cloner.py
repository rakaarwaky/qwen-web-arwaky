"""Utility layer: Chromium session cloning and ephemeral profile management.

Enables 1-browser-per-job parallel execution with shared login sessions
by creating isolated temporary clones of the master profile directory.

Materialization is O(delta) rather than O(full profile): only the immutable
resource files Chromium ships into the profile are hardlinked from the master
(so they cost a directory entry, not a copy), while every file Chromium may
write — cookies, preferences, LevelDB, caches, logs — is copied. No global
lock serializes the clones, so parallel browser startup does not queue behind
the slowest copy; only stale-lock cleanup of the master profile is
synchronized.

Security (issue #346): clones carry live authentication cookies, so they are
created under ``$XDG_RUNTIME_DIR`` (a tmpfs cleared at logout) whenever it is
available, orphaned clones left behind by a ``SIGKILL`` or power loss are
swept at process start, and :func:`session_age_warning` reports the master
profile age so operators can re-login before IdP expiry.
"""

from __future__ import annotations

import contextlib
import fnmatch
import logging
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: Serializes stale-lock cleanup of the *master* profile only. Clone
#: materialization never takes this lock, so concurrent startups overlap.
_MASTER_LOCKS_LOCK = threading.Lock()

STALE_LOCK_PATTERNS = ("SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort")

#: Glob patterns of files Chromium never writes back. Everything else — cookies,
#: ``Preferences``, ``Local State``, the whole LevelDB tree, caches, logs — is
#: copied, because a hardlinked inode would let the clone's writes corrupt the
#: master profile. Hardlinking is a directory-entry operation, so these cost
#: nothing per byte and stay the bulk of a stock profile.
_IMMUTABLE_GLOBS = ("*.pak", "*.bin")
_IMMUTABLE_DIRS = ("locales",)

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


def _is_immutable(name: str, path: Path) -> bool:
    """True when *path* is a Chromium resource Chromium never writes back.

    Symlinks are reproduced as symlinks rather than linked, and directories are
    materialized entry by entry, so neither is a hardlink candidate here.
    """
    if path.is_symlink() or path.is_dir():
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in _IMMUTABLE_GLOBS)


def _link_tree(src: Path, dst: Path) -> None:
    """Hardlink an immutable resource tree, falling back to a copy.

    Returns ``False`` when the fallback was needed, so the caller can report
    a profile that was not fully hardlinked.
    """
    # Create the destination root first: a file directly inside *src* links to
    # dst/<name>, and both os.link and shutil.copy2 fail if dst itself is
    # missing.
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _link_tree(item, target)
        else:
            try:
                os.link(item, target)
            except OSError:
                # Cross-device link or a file removed mid-clone: copying the
                # bytes is always correct, just slower.
                shutil.copy2(item, target, follow_symlinks=False)


def _copy_profile_overlay(src: Path, dst: Path) -> None:
    """Materialize *dst* as a hardlink-overlay copy of *src*.

    Immutable files matching ``_IMMUTABLE_GLOBS`` are hardlinked from the
    source so they cost a directory entry, not a full copy.  Everything else —
    mutable state and immutable resource directories — is copied verbatim.
    The master profile is only read, so clones never contend for a write and
    no lock is required.
    """
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_symlink():
            with contextlib.suppress(OSError):
                os.symlink(os.readlink(item), target)
        elif item.is_dir() and item.name in _IMMUTABLE_DIRS:
            _link_tree(item, target)
        elif item.is_dir():
            shutil.copytree(
                item, target, symlinks=True, ignore=shutil.ignore_patterns("Singleton*", "DevToolsActivePort")
            )
        elif _is_immutable(item.name, item):
            try:
                os.link(item, target)
            except OSError:
                # Cross-device link or a file removed mid-clone: copying the
                # bytes is always correct, just slower.
                shutil.copy2(item, target, follow_symlinks=False)
        else:
            shutil.copy2(item, target)


def clone_session_profile(src: Path, dst: Path) -> None:
    """Clone master profile files into destination directory, ignoring locks and broken symlinks.

    Only the master's stale-lock cleanup is serialized; the overlay copy itself
    runs unguarded so parallel job startup overlaps instead of queueing.
    """
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists() or not src.is_dir():
        with contextlib.suppress(OSError):
            dst.chmod(0o700)
        return

    with _MASTER_LOCKS_LOCK:
        clean_stale_locks(src)
    _copy_profile_overlay(src, dst)

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
    with _MASTER_LOCKS_LOCK:
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
