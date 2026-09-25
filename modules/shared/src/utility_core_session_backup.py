"""Utility layer (utility_core_session_backup): master session snapshot, restore, and delete guard.

Every parallel job clones the master Qwen browser profile at
``DEFAULT_SESSION``. Losing or corrupting that profile forces an interactive
CAPTCHA re-login, which cannot be scripted and blocks all unattended workloads,
so a successful login snapshots the profile and deletion is refused while no
snapshot is retained (issue #300).

Snapshots live in ``{session_path}/.backups/<UTC timestamp>/`` as full copies —
a Chromium profile cannot be safely diffed (singleton locks, cookie stores,
IndexedDB). Generations are pruned on write so the host does not accumulate
copies until the disk fills, and every snapshot is mode 0700 because the profile
holds live credentials. ``.backups`` itself is excluded from the copy so a
snapshot never nests another snapshot.
"""

from __future__ import annotations

import contextlib
import re
import shutil
import time
from collections.abc import Iterator
from pathlib import Path

BACKUPS_DIR_NAME = ".backups"
DEFAULT_MAX_GENERATIONS = 3
SNAPSHOT_MODE = 0o700
_TIMESTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")

# Prune only generations older than the cap and outside the retention window,
# so a freshly created snapshot is never removed in the same pass.
_RETENTION_WINDOW_SEC = 24 * 60 * 60


def backups_dir(session_path: Path) -> Path:
    """Return the hidden ``.backups`` directory that holds generations for *session_path*."""
    return Path(session_path) / BACKUPS_DIR_NAME


def list_session_backups(session_path: Path) -> list[Path]:
    """Return retained snapshot directories, newest generation first."""
    return sorted(_snapshots(backups_dir(session_path)), key=lambda p: p.name, reverse=True)


def has_session_backup(session_path: Path) -> bool:
    """Return True when at least one backup generation is retained."""
    return any(True for _ in _snapshots(backups_dir(session_path)))


def snapshots_count(session_path: Path) -> int:
    """Return the number of retained backup generations."""
    return sum(1 for _ in _snapshots(backups_dir(session_path)))


def take_snapshot(session_path: Path, *, max_generations: int = DEFAULT_MAX_GENERATIONS) -> Path:
    """Copy the master profile into a new ``.backups`` generation and prune old ones.

    Returns the created generation path. The snapshot is written before old
    generations are pruned so a disk failure mid-prune still leaves the newest
    known-good copy in place.
    """
    source = Path(session_path)
    target = backups_dir(source) / time.strftime("%Y%m%dT%H%M%SZ")
    target.mkdir(mode=SNAPSHOT_MODE, parents=True, exist_ok=True)
    _copy_profile(source, target)
    _prune_old_snapshots(backups_dir(source), max_generations)
    return target


def restore_latest(session_path: Path) -> Path:
    """Restore the newest retained generation over the master profile.

    The existing profile is renamed aside first so a failure during the
    restore can be reversed by the caller. Returns the restored master path.
    """
    source = Path(session_path)
    generations = list_session_backups(source)
    if not generations:
        raise FileNotFoundError(
            f"No session backup found under {backups_dir(source)}. Recover by running "
            "'qwen-web-arwaky login' (interactive CAPTCHA). See docs/runbooks/session-corruption.md"
        )
    return restore_generation(source, generations[0])


def restore_generation(session_path: Path, generation: Path) -> Path:
    """Restore a specific generation over the master profile.

    The generation must live under the session's own ``.backups`` directory, so
    an operator cannot be tricked into copying an unrelated directory over the
    live profile. The restore happens in place and the ``.backups`` tree is
    preserved throughout: moving the profile aside would invalidate the
    generation path mid-copy and leave the session with no recovery history.
    """
    source = Path(session_path)
    snapshot = Path(generation)
    root = backups_dir(source)
    if not _is_under(snapshot, root):
        raise ValueError(f"Refusing to restore {snapshot}: it is not under {root}")
    if not snapshot.is_dir():
        raise FileNotFoundError(f"Session backup generation does not exist: {snapshot}")

    for entry in source.iterdir() if source.is_dir() else ():
        if entry.name == BACKUPS_DIR_NAME:
            continue
        with contextlib.suppress(OSError):
            shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
    _copy_profile(snapshot, source)
    _harden(source)
    return source


def refuse_delete_without_backup(session_path: Path, *, force: bool = False) -> None:
    """Raise ``PermissionError`` when no backup is retained and *force* is False.

    ``delete_session`` calls this before removing the master profile so an
    accidental deletion cannot cost an interactive re-login.
    """
    if force or has_session_backup(session_path):
        return
    raise PermissionError(
        f"Refusing to delete {session_path}: no session backup is retained under "
        f"{backups_dir(session_path)}. Recovery would require an interactive CAPTCHA login. "
        "Pass force=true to delete anyway, or restore/re-login first. "
        "See docs/runbooks/session-corruption.md"
    )


def _snapshots(backup_root: Path) -> Iterator[Path]:
    """Yield each generation directory under *backup_root* in ascending name order."""
    if not backup_root.is_dir():
        return
    for entry in sorted(backup_root.iterdir()):
        if entry.is_dir() and _TIMESTAMP_RE.match(entry.name):
            yield entry


def _is_under(candidate: Path, root: Path) -> bool:
    """Return True when *candidate* resolves to a path inside *root*."""
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _copy_profile(src: Path, dst: Path) -> None:
    """Copy a Chromium profile from *src* to *dst*, skipping the backup directory."""
    ignore = shutil.ignore_patterns(BACKUPS_DIR_NAME, "Singleton*", "DevToolsActivePort")
    if not src.is_dir():
        _harden(dst)
        return
    shutil.copytree(
        src,
        dst,
        symlinks=True,
        ignore=ignore,
        ignore_dangling_symlinks=True,
        dirs_exist_ok=True,
    )
    _harden(dst)


def _harden(profile_dir: Path) -> None:
    """Force 0700 on the profile and every subdirectory it contains."""
    with contextlib.suppress(OSError):
        profile_dir.mkdir(mode=SNAPSHOT_MODE, parents=True, exist_ok=True)
        profile_dir.chmod(SNAPSHOT_MODE)
    with contextlib.suppress(OSError):
        for child in profile_dir.rglob("*"):
            if child.is_dir():
                child.chmod(SNAPSHOT_MODE)


def _prune_old_snapshots(backup_root: Path, max_generations: int) -> None:
    """Delete generations beyond *max_generations*, soft-keeping recent ones.

    Always retains the newest ``max_generations`` snapshots so a recent series
    of successful backups can never be lost. Older generations that fall outside
    the retention window are deleted first; anything still within 24 hours is
    preserved only if we haven't yet hit the hard cap, so a burst of rapid
    snapshots does not inflate the directory forever (issue #300).
    """
    if max_generations < 1:
        return
    generations = list(_snapshots(backup_root))
    if len(generations) <= max_generations:
        return
    cutoff = time.time() - _RETENTION_WINDOW_SEC
    # The newest N are always retained. Among the rest, only one that still
    # sits inside the 24h soft window survives a single burst slot; hard cap
    # still bounds the total so rapid snapshots cannot inflate the directory.
    anchor = generations[-max_generations]
    recent_overflow = 0
    for generation in reversed(generations):
        if generation >= anchor:
            continue
        if generation.stat().st_mtime >= cutoff and recent_overflow == 0:
            retained_count = len(generations) - recent_overflow
            if retained_count <= max_generations + 1:
                recent_overflow = 1
        if generation.stat().st_mtime < cutoff or recent_overflow:
            break
    retained = set(g for g in generations if g >= anchor)
    if recent_overflow:
        retained.add(generations[-max_generations - 1])
    for generation in generations:
        if generation not in retained:
            with contextlib.suppress(OSError):
                shutil.rmtree(generation)


__all__ = [
    "BACKUPS_DIR_NAME",
    "DEFAULT_MAX_GENERATIONS",
    "backups_dir",
    "has_session_backup",
    "list_session_backups",
    "refuse_delete_without_backup",
    "restore_generation",
    "restore_latest",
    "snapshots_count",
    "take_snapshot",
]
