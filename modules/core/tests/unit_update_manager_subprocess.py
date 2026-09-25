"""Unit tests for UpdateManager subprocess execution (issue #334).

``UpdateManager._run_subprocess`` is the security-sensitive boundary of the
self-update pipeline: every argument is validated against shell
metacharacters, absolute paths are restricted to allowed roots, and the
executable is mapped through ``_approved_spawn_command`` so only ``git`` and
``sys.executable -m pip`` / ``-m playwright`` ever reach the child process.

The manager runs every child through the stdlib ``subprocess`` layer rather
than a POSIX-only primitive (issue #367), so the timeout and exit-code
branches that used to be driven by a mocked ``os.posix_spawn`` /
``os.waitpid`` polling loop are now covered by the ``subprocess.run`` contracts
exercised below: ``TimeoutExpired`` → 124, ``FileNotFoundError`` → 127, and
any other ``OSError`` → 1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.core.src.capabilities_update_manager import UpdateManager

FORBIDDEN = UpdateManager._SUBPROCESS_FORBIDDEN_CHARS

METACHAR_MSG = "shell metacharacters"
OUTSIDE_ROOTS_MSG = "outside allowed roots"
UNSUPPORTED_MSG = "Unsupported update command"


def _mgr() -> UpdateManager:
    """Build an update manager with the default package and timeouts."""
    return UpdateManager()


# ── Argument validation ──────────────────────────────────────────────────────


@pytest.mark.parametrize("char", [";", "&", "|", "$", "`", ">", "<", "\n", "\r"])
def test_run_subprocess_rejects_each_shell_metacharacter(char: str) -> None:
    """Every shell metacharacter is refused before any process is spawned."""
    rc, out, err = _mgr()._run_subprocess(["git", f"-C{char}/tmp/evil"], timeout_sec=1.0)
    assert rc == 1
    assert out == ""
    assert METACHAR_MSG in err


def test_run_subprocess_rejects_shell_metacharacters() -> None:
    """A metacharacter embedded mid-argument is refused, not just a leading one."""
    rc, out, err = _mgr()._run_subprocess(["git", "status", "HEAD&evil"], timeout_sec=1.0)
    assert rc == 1
    assert out == ""
    assert METACHAR_MSG in err


def test_run_subprocess_rejects_null_byte() -> None:
    """A NUL byte truncates argv at the C level, so it must be refused too.

    ``git`` and ``pip`` both parse their arguments as NUL-terminated C strings;
    an unrefused NUL would silently split one validated argument into two
    unvalidated ones.
    """
    rc, out, err = _mgr()._run_subprocess(["git", "checkout", "main\0--force"], timeout_sec=1.0)
    assert rc == 1
    assert out == ""
    assert METACHAR_MSG in err
    assert "\0" in FORBIDDEN


def test_forbidden_set_is_exactly_the_documented_characters() -> None:
    """The guard set is pinned so a new metacharacter cannot slip in unnoticed."""
    assert set(";&|$`><\n\r\0") == FORBIDDEN


def test_guard_set_excludes_safe_path_characters() -> None:
    """Spaces, dashes, dots and equals appear in every legitimate path, so stay allowed."""
    assert " " not in FORBIDDEN
    assert "-" not in FORBIDDEN
    assert "." not in FORBIDDEN
    assert "=" not in FORBIDDEN


def test_run_subprocess_rejects_path_outside_allowed_roots() -> None:
    """Absolute paths outside the project/home/toolchain roots are refused."""
    rc, _out, err = _mgr()._run_subprocess(["git", "-C", "/etc/passwd"], timeout_sec=1.0)
    assert rc == 1
    assert OUTSIDE_ROOTS_MSG in err


def test_run_subprocess_rejects_path_outside_allowed_roots_in_tmp(tmp_path: Path) -> None:
    """A real file under a disallowed root is refused before approval runs."""
    rogue = tmp_path / "rogue.bin"
    rogue.touch()
    rc, _out, err = _mgr()._run_subprocess([str(rogue)], timeout_sec=1.0)
    assert rc == 1
    assert OUTSIDE_ROOTS_MSG in err


def test_run_subprocess_accepts_path_under_allowed_root() -> None:
    """A path inside an allowed root passes the containment guard.

    ``sys.base_prefix`` is one of the three allowed roots, so it is the only
    path guaranteed to be accepted regardless of where the checkout lives.  The
    command is still unapproved, so the run fails — but with the approval
    error, not the containment error.
    """
    rc, _out, err = _mgr()._run_subprocess([sys.executable, sys.base_prefix, "--version"], timeout_sec=1.0)
    assert OUTSIDE_ROOTS_MSG not in err
    assert UNSUPPORTED_MSG in err


def test_shell_metacharacter_in_path_argument_is_refused(tmp_path: Path) -> None:
    """A path argument containing ``;`` is refused even inside a nominal root."""
    rogue = tmp_path / "ev il;rm -rf"
    rogue.touch()
    rc, _out, err = _mgr()._run_subprocess([str(rogue)], timeout_sec=1.0)
    assert rc == 1
    assert METACHAR_MSG in err


# ── Approved command mapping ─────────────────────────────────────────────────


def test_approved_spawn_command_maps_git() -> None:
    """``git`` commands pass through with argv intact."""
    argv = ["git", "-C", "/path", "pull"]
    assert UpdateManager._approved_spawn_command(argv) == argv


@pytest.mark.parametrize("module", ["pip", "playwright"])
def test_approved_spawn_command_maps_python_modules(module: str) -> None:
    """``sys.executable -m pip`` / ``-m playwright`` pass through as-is.

    The allow-list is positional (``-m`` at index 1, a known module at index
    2), so these are the only two module invocations admitted; every other
    module name raises.
    """
    argv = [sys.executable, "-m", module, "install", "chromium"]
    assert UpdateManager._approved_spawn_command(argv) == argv


def test_approved_spawn_command_rejects_unknown_module() -> None:
    """An arbitrary module name is not admitted even under the right executable."""
    with pytest.raises(ValueError, match=UNSUPPORTED_MSG):
        UpdateManager._approved_spawn_command([sys.executable, "-m", "os", "system"])


def test_approved_spawn_command_rejects_rm_rf_root() -> None:
    """``rm -rf /`` is never admitted because it is not git or a known python -m module."""
    with pytest.raises(ValueError, match=UNSUPPORTED_MSG):
        UpdateManager._approved_spawn_command(["rm", "-rf", "/"])


@pytest.mark.parametrize(
    "cmd",
    [
        ["rm", "-rf", "/"],
        ["curl", "https://example.com"],
        ["/bin/sh", "-c", "echo hi"],
        ["python3", "-c", "import os; os.remove('/etc/shadow')"],
        [],
    ],
)
def test_approved_spawn_command_refuses_everything_else(cmd: list[str]) -> None:
    """Any other argv shape raises so no arbitrary executables can be spawned."""
    with pytest.raises(ValueError, match=UNSUPPORTED_MSG):
        UpdateManager._approved_spawn_command(cmd)


def test_unapproved_command_never_reaches_subprocess() -> None:
    """``_approved_spawn_command`` refusal happens before any spawn attempt.

    A command whose arguments all land inside an allowed root but whose first
    argument is not ``git`` or the recognised ``-m``/module pair is refused by
    the approval path.  The error must be ``Unsupported update command``, not an
    ``OSError`` from a missing executable.
    """
    with patch("subprocess.run") as run:
        rc, _out, err = _mgr()._run_subprocess(
            [sys.executable, "-m", "http", "server"],
            timeout_sec=1.0,
        )
    assert rc == 1
    assert UNSUPPORTED_MSG in err
    run.assert_not_called()


def test_unapproved_command_is_refused_before_spawn() -> None:
    """Refusal happens before the child launch, not after path validation."""
    manager = _mgr()
    with patch.object(manager, "_approved_spawn_command", side_effect=ValueError("nope")) as approve:
        with patch("subprocess.run") as run:
            rc, _out, _err = manager._run_subprocess(["curl", "http://evil.example"], timeout_sec=1.0)
            assert rc == 1
            approve.assert_called_once_with(["curl", "http://evil.example"])
            run.assert_not_called()


# ── Execution / timeout contract (subprocess.run) ────────────────────────────


def test_subprocess_run_path_returns_returncode_zero_when_command_succeeds() -> None:
    """A successful command returns the child transcript and exit code 0."""
    manager = _mgr()
    with patch("subprocess.run") as run:
        completed = run.return_value
        completed.returncode = 0
        completed.stdout = b"git version 2.43.0"
        completed.stderr = b""
        rc, out, err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
    assert rc == 0
    assert out == "git version 2.43.0"
    assert err == ""


def test_subprocess_run_path_surfaces_nonzero_returncode() -> None:
    """A failing command returns the child's own exit code and stderr."""
    manager = _mgr()
    with patch("subprocess.run") as run:
        completed = run.return_value
        completed.returncode = 128
        completed.stdout = b""
        completed.stderr = b"fatal: not a git repository"
        rc, out, err = manager._run_subprocess(["git", "status"], timeout_sec=1.0)
    assert rc == 128
    assert out == ""
    assert "not a git repository" in err


def test_timeout_returns_124() -> None:
    """A subprocess that outlives its deadline returns the 124 contract."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["git", "status"], timeout=0.0)):
        rc, _out, err = _mgr()._run_subprocess(["git", "status"], timeout_sec=0.0)
    assert rc == 124
    assert "timed out" in err.lower()


def test_subprocess_timeout_expired_returns_124() -> None:
    """Timeout in the subprocess.run path returns rc 124 instead of raising."""
    manager = _mgr()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["sleep", "999"], timeout=5.0)):
        rc, _out, err = manager._run_subprocess(["git", "status"], timeout_sec=5.0)
    assert rc == 124
    assert "timed out" in err.lower()


def test_missing_executable_returns_127() -> None:
    """FileNotFoundError from subprocess.run surfaces as rc=127."""
    with patch("subprocess.run", side_effect=FileNotFoundError("no git here")):
        rc, _out, err = _mgr()._run_subprocess(["git", "status"], timeout_sec=1.0)
    assert rc == 127
    assert "Executable not found" in err


def test_spawn_failure_returns_1() -> None:
    """A generic OSError from the launch is surfaced as a refusal (rc=1)."""
    manager = _mgr()
    with patch("subprocess.run", side_effect=OSError("spawn failed")):
        rc, _out, err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
    assert rc == 1
    assert "spawn failed" in err


def test_waitpid_oserror_is_surfaced() -> None:
    """Any unexpected launch error aborts the process and returns rc=1."""
    manager = _mgr()
    with patch("subprocess.run", side_effect=OSError("wait failed")):
        rc, _out, err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
    assert rc == 1
    assert "wait failed" in err
