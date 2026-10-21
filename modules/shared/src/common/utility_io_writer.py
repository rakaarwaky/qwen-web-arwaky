"""Filesystem writer utilities.

Utility layer (utility_io_writer): atomic file writing, JSONL append,
and directory creation helpers. Stateless functions consumed by Saver
and StatusFileWriter.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from modules.shared.src.common.taxonomy_core_constant import DEFAULT_METADATA_DIR, DEFAULT_OUTPUT
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import OutputWriteError
from modules.shared.src.common.taxonomy_core_event import EVENT_OUTPUT_COPIED

#: Suffix appended to in-flight atomic writes. Deliberately not a ``.json``/
#: ``.md`` extension so directory scans (e.g. ``JobStorage.list_jobs`` globbing
#: ``*.json``) never pick up a partial write, and so real records are free to
#: contain arbitrary substrings without being mistaken for temp artifacts.
ATOMIC_TEMP_SUFFIX = ".tmpwrite"

#: Owner-only mode the lock file is forced to, independent of umask.
_LOCK_FILE_MODE = 0o600
#: How long to keep polling a contended lock before giving up, and the poll
#: interval. Bounded so a crashed holder cannot park every later writer.
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_INTERVAL = 0.05


def _lock_open_flags() -> int:
    """Open flags for the lock file; ``msvcrt.locking`` needs a writable fd."""
    if sys.platform == "win32":
        return os.O_CREAT | os.O_RDWR
    flags = os.O_CREAT | os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _try_lock(fd: int) -> bool:
    """Take a non-blocking exclusive lock; True when acquired."""
    if sys.platform == "win32":
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _release_lock(fd: int) -> None:
    """Drop the exclusive lock held on *fd*; best-effort."""
    if sys.platform == "win32":
        import msvcrt

        with suppress(OSError):
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    with suppress(OSError):
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def exclusive_file_lock(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock on *lock_path* for the block's duration.

    Cross-process serialization for read-modify-write cycles (``fcntl.flock``
    on POSIX, ``msvcrt.locking`` on Windows). Polls up to
    ``LOCK_TIMEOUT_SECONDS`` so concurrent holders serialize rather than
    fail; a timeout raises ``OutputWriteError`` so the caller surfaces a
    named failure instead of silently losing the write.
    """
    try:
        fd = os.open(str(lock_path), _lock_open_flags(), _LOCK_FILE_MODE)
    except OSError as exc:
        raise OutputWriteError(f"could not open lock file {lock_path}: {exc}") from exc
    try:
        with suppress(OSError):
            os.chmod(str(lock_path), _LOCK_FILE_MODE)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                raise OutputWriteError(f"could not acquire lock on {lock_path} within {LOCK_TIMEOUT_SECONDS}s")
            time.sleep(LOCK_POLL_INTERVAL)
        try:
            yield
        finally:
            _release_lock(fd)
    finally:
        with suppress(OSError):
            os.close(fd)


def _atomic_write(target: Path, content: str, mode: int = 0o600) -> None:
    """Write content to a file atomically via temp + replace with secure file mode (Issue #353).

    The mode is applied to the temp file **before** the rename, so no window
    exists where the destination is world/group-readable, and re-asserted
    on the destination afterwards because ``os.replace`` preserves the
    source inode when the target already exists with looser permissions.

    Parameters
    ----------
    target : Path
        Destination file path.
    content : str
        Text content to write.
    mode : int, optional
        Filesystem permissions to enforce, by default 0o600 (owner read/write only).

    """
    tmp_path = target.with_name(target.name + ATOMIC_TEMP_SUFFIX)
    try:
        tmp_path.write_text(content, encoding="utf-8")
        with suppress(OSError):
            tmp_path.chmod(mode)
        tmp_path.replace(target)
        with suppress(OSError):
            target.chmod(mode)
    except OSError as err:
        if tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()
        raise OutputWriteError(f"Atomic write failed for {target}: {err}") from err


atomic_write_text = _atomic_write


def atomic_write_json(target: Path, payload: Mapping[str, Any]) -> None:
    """Atomically write JSON to a file via temp + rename."""
    _atomic_write(target, json.dumps(payload, ensure_ascii=False) + "\n")


def write_json_file(target: Path, payload: Mapping[str, Any], atomic: bool = True, mode: int = 0o600) -> None:
    """Write JSON to file, atomically or directly with confidentiality defaults (Issue #353)."""
    content = json.dumps(payload, ensure_ascii=False) + "\n"
    if atomic:
        _atomic_write(target, content, mode=mode)
    else:
        target.write_text(content, encoding="utf-8")
        with suppress(OSError):
            target.chmod(mode)


def ensure_dir(path: Path) -> Path:
    """Create parent directories for *path* if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def sidecar_path_for(output_path: Path, metadata_dir: Path | None = None) -> Path:
    """Map an output artifact to its ``.meta.json`` under the XDG meta root.

    Sidecars mirror the artifact's path relative to ``DEFAULT_OUTPUT`` so the
    output directory holds only prompt responses. Paths outside
    ``DEFAULT_OUTPUT`` nest their absolute path (sans root) under the meta
    root, so two destinations that share a basename never collide.
    """
    root = (metadata_dir or DEFAULT_METADATA_DIR).resolve()
    out = Path(output_path).resolve()
    try:
        rel = out.relative_to(DEFAULT_OUTPUT.resolve())
    except ValueError:
        parts = out.parts[1:] if out.is_absolute() else out.parts
        rel = Path(*parts) if parts else Path(out.name)
    return root / rel.with_suffix(".meta.json")


def save_orchestrator_output(
    saver: Any,
    out_path: Path,
    p_path: Path,
    text: str,
    dur: float,
    ctx: Any,
    emitter: LifecycleEmitter | None = None,
) -> None:
    """Save output and emit the terminal event only after filesystem verification."""
    from modules.shared.src.common.taxonomy_core_vo import FilePath, OutputChars, ResponseText

    prompt_len = p_path.stat().st_size if p_path.exists() else 0
    saver.write_output(
        out_path,
        ResponseText(text),
        ctx,
        FilePath(p_path),
        dur,
        prompt_len,
        OutputChars(len(text)),
    )
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise OutputWriteError(f"Output saver returned without a readable file: {out_path}")
    if emitter is not None:
        emitter.emit(
            EVENT_OUTPUT_COPIED,
            {"path": str(out_path), "bytes": out_path.stat().st_size},
        )
