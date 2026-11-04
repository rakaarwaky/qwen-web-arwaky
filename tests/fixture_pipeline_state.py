"""Pipeline fixture helpers and golden task state management for tests."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

_MIN_RUN_INTERVAL_SECS = 2.0


def restore_fixture_state(fixture_root: Path, force: bool = False) -> None:
    """Restores tests/fixtures/ to pristine state if run threshold elapsed."""
    ts_file = fixture_root / ".last_run_ts"
    now = time.time()

    if not force and ts_file.exists():
        try:
            last_run = float(ts_file.read_text(encoding="utf-8").strip())
            if now - last_run < _MIN_RUN_INTERVAL_SECS:
                return
        except ValueError:
            pass

    _clean_output_dirs(fixture_root)
    ts_file.write_text(str(now), encoding="utf-8")


def _clean_output_dirs(fixture_root: Path) -> None:
    output_dir = fixture_root / "output"
    if output_dir.exists():
        for out_sub in output_dir.iterdir():
            if out_sub.is_dir():
                shutil.rmtree(out_sub, ignore_errors=True)
            elif out_sub.is_file() and out_sub.name != ".gitkeep":
                out_sub.unlink(missing_ok=True)

    log_dir = fixture_root / "log"
    if log_dir.exists():
        for log_file in log_dir.glob("*"):
            if log_file.is_file() and log_file.name != ".gitkeep":
                log_file.unlink(missing_ok=True)
