"""Update subprocess sandbox (utility layer).

The security-sensitive boundary every update command flows through,
split out of ``utility_update_pipeline.py``. Callers pass an allowlisted
argv; the sandbox refuses shell metacharacters and absolute paths outside
the project root / user home / toolchain prefix, then spawns through the
stdlib ``subprocess`` layer so the same code path serves every platform.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

__all__ = [
    "SUBPROCESS_FORBIDDEN_CHARS",
    "approved_spawn_command",
    "decode_output",
    "run_subprocess",
    "run_pip_show",
    "tail",
]

log = logging.getLogger("utility_update_subprocess")

#: Shell metacharacters refused in every subprocess argument. ``\0`` would
#: truncate the argument at the C level (argv is NUL-joined), so it is
#: refused alongside the others.
SUBPROCESS_FORBIDDEN_CHARS = set(";&|$`><\n\r\0")


def tail(text: str | None, max_chars: int = 400) -> str:
    """Return the trailing slice of a subprocess transcript for compact error detail."""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"...{cleaned[-max_chars:]}"


def decode_output(data: bytes | str | None) -> str:
    """Decode captured process output without allowing invalid bytes to escape."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return bytes(data).decode("utf-8", errors="replace")


def approved_spawn_command(cmd: list[str]) -> list[str]:
    """Map a validated update command onto a fixed, platform-neutral argv.

    ``git`` is invoked directly; ``-m pip`` / ``-m playwright`` run under the
    *current* interpreter rather than a hard-coded ``python3`` so the update
    targets the environment it was launched from on every platform.
    """
    if cmd and cmd[0] == "git":
        return [*cmd]
    if len(cmd) >= 3 and cmd[0] == sys.executable and cmd[1:2] == ["-m"] and cmd[2] in {"pip", "playwright"}:
        return [*cmd]
    raise ValueError("Unsupported update command")


def run_subprocess(cmd: list[str], *, timeout_sec: float = 60.0) -> tuple[int, str, str]:
    """Run a validated subprocess, capturing transcripts portably.

    Defensive validation: every argument must be free of shell metacharacters,
    and any absolute path argument must live under the project root, the user
    home directory, or a standard system toolchain location — preventing
    injection via manipulated package metadata or environment variables.
    """
    for arg in cmd:
        if any(ch in arg for ch in SUBPROCESS_FORBIDDEN_CHARS):
            log.error("subprocess_rejected_argument arg=%r", arg)
            return 1, "", f"Refusing subprocess argument with shell metacharacters: {arg}"
        if arg.startswith("/"):
            p = Path(arg)
            allowed_roots = (
                Path(__file__).resolve().parents[3],
                Path.home(),
                Path(sys.base_prefix),
            )
            if not any(root == p or root in p.parents for root in allowed_roots):
                log.error("subprocess_rejected_path arg=%r", arg)
                return 1, "", f"Refusing subprocess path outside allowed roots: {arg}"
    try:
        spawn_cmd = approved_spawn_command(cmd)
    except ValueError as exc:
        log.error("subprocess_rejected_command cmd=%r", cmd)
        return 1, "", str(exc)

    import subprocess  # nosec B404 - allowlisted argv, shell=False

    try:
        proc = subprocess.run(  # nosec B603 - allowlisted argv, shell=False
            spawn_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        log.error("subprocess_timeout cmd=%r timeout=%s", cmd, timeout_sec)
        return 1, "", f"Subprocess timed out after {timeout_sec}s: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        log.error("subprocess_failed cmd=%r error=%s", cmd, exc)
        return 1, "", f"Subprocess failed: {exc}"


def run_pip_show(package_name: str) -> tuple[int, str, str]:
    """Run ``pip show <package>`` via the validated subprocess sandbox."""
    return run_subprocess([sys.executable, "-m", "pip", "show", package_name], timeout_sec=60.0)
