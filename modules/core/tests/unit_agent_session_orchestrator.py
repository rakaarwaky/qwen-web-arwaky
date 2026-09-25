"""Unit tests for the session deletion path-safety guard (issue #337).

``SessionOrchestrator.delete_session`` calls ``shutil.rmtree``, so the path
it is handed must be vetted before the delete happens.  The dangerous shapes
on POSIX (``/``, ``/etc``) are not the only ones: ``DEFAULT_SESSION`` is
resolved from ``LOCALAPPDATA`` on Windows, so drive roots (``C:\\``) and
near-root directories (``C:\\Windows``) have to be refused too.  These tests
exercise the guard on both path flavours with a mocked ``Path.home`` so the
rules are covered on any host OS.

The positive case uses a temp directory registered as a safe session target,
so no real user profile is ever touched.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.agent_session_orchestrator import SessionOrchestrator
from modules.core.src.utility_core_session_guard import is_filesystem_root, is_safe_session_target
from modules.shared.src.taxonomy_core_error import QwenCliError


def _orchestrator() -> SessionOrchestrator:
    return SessionOrchestrator(browser=MagicMock(), observability=MagicMock())


# ── Refusals: filesystem roots and near-root paths ───────────────────────────


@pytest.mark.parametrize("raw", ["/", "//", "/..", "/etc", "/usr", "/home"])
def test_posix_roots_and_near_roots_are_refused(raw: str, tmp_path: Path) -> None:
    """POSIX roots and shallow system directories must never be deletable."""
    assert is_safe_session_target(Path(raw).resolve()) is False


def test_home_directory_itself_is_refused() -> None:
    """The user's home is never a session target, even if it exists."""
    assert is_safe_session_target(Path.home().resolve()) is False


def test_top_level_home_child_without_safe_name_is_refused() -> None:
    """``~/Documents`` is under home but is not a safe session name."""
    docs = Path.home() / "Documents"
    assert is_safe_session_target(docs) is False


def test_windows_drive_root_is_recognized_as_filesystem_root() -> None:
    """``C:\\`` is a filesystem root even when parsed on POSIX."""
    assert is_filesystem_root(PureWindowsPath("C:\\")) is True
    assert is_filesystem_root(PureWindowsPath("C:/Users")) is False


def test_non_directory_target_is_refused(tmp_path: Path) -> None:
    """A regular file is never a session target, whatever its name."""
    target = tmp_path / "qwen_session"
    target.write_text("not a profile", encoding="utf-8")
    assert is_safe_session_target(target) is False


def test_relative_path_is_refused() -> None:
    """Relative paths must be refused — they resolve against the CWD."""
    assert is_safe_session_target(Path("qwen_session")) is False


# ── Allowances ───────────────────────────────────────────────────────────────


def test_default_session_directory_is_allowed(tmp_path: Path) -> None:
    """The application's own session directory stays deletable."""
    fake_default = tmp_path / "share" / "qwen-web-arwaky" / "qwen_session"
    fake_default.mkdir(parents=True)
    with patch("modules.core.src.utility_core_session_guard.DEFAULT_SESSION", fake_default):
        assert is_safe_session_target(fake_default) is True


def test_child_of_default_session_is_allowed(tmp_path: Path) -> None:
    """Anything inside the application session directory is in scope."""
    fake_default = tmp_path / "share" / "qwen_session"
    child = fake_default / "Default"
    child.mkdir(parents=True)
    with patch("modules.core.src.utility_core_session_guard.DEFAULT_SESSION", fake_default):
        assert is_safe_session_target(child) is True


def test_safe_session_name_under_home_is_refused(tmp_path: Path) -> None:
    """A directory named ``qwen_session`` under home but outside DEFAULT_SESSION must be refused.

    Issue #345: the old "safe_name + under_home" branch permitted deletion of
    any ``session``-named directory under the user's home tree, e.g.
    ``~/projects/session``.  That branch is removed; only DEFAULT_SESSION
    and its strict descendants are allowed.
    """
    fake_home = tmp_path / "home"
    target = fake_home / "projects" / "session"
    target.mkdir(parents=True)
    assert is_safe_session_target(target) is False


# ── Orchestrator behaviour ───────────────────────────────────────────────────


def test_delete_session_refuses_posix_root(tmp_path: Path) -> None:
    """``delete_session`` must refuse ``/`` with the documented error."""
    orch = _orchestrator()
    with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False):
        with patch("modules.core.src.agent_session_orchestrator.build_app_config") as build:
            build.return_value.session_path = Path("/")
            with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
                orch.delete_session()


def test_delete_session_refuses_etc(tmp_path: Path) -> None:
    """A near-root system directory must be refused before ``rmtree``."""
    orch = _orchestrator()
    with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False):
        with patch("modules.core.src.agent_session_orchestrator.build_app_config") as build:
            build.return_value.session_path = Path("/etc")
            with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
                orch.delete_session()


def test_delete_session_refuses_windows_drive_root() -> None:
    """Cross-platform: the path safety check handles Windows path shapes.

    ``PureWindowsPath`` reproduces the real Windows ``parts`` layout
    (``('C:\\',)`` for a drive root, ``('C:\\', 'Windows')`` for a near-root
    directory) on any host, so both refusals are locked without needing a
    Windows machine.  The drive root is a filesystem root; the near-root
    directory has fewer than ``_PARTS_FLOOR`` components.
    """
    assert is_filesystem_root(PureWindowsPath("C:\\")) is True
    assert is_filesystem_root(PureWindowsPath("D:\\")) is True
    assert len(PureWindowsPath("C:\\Windows").parts) < 3
    # A real session under a Windows home clears the floor:
    assert len(PureWindowsPath("C:\\Users\\me\\qwen_session").parts) >= 3
    # And the POSIX spelling of a drive root is refused when non-absolute.
    assert is_safe_session_target(Path("C:\\")) is False


def test_delete_session_refuses_session_named_dir_under_home(tmp_path: Path) -> None:
    """Issue #345: ``~/projects/session``-shaped paths must raise and delete nothing.

    The pre-fix guard authorised any ``session``/``qwen_session``-named
    directory under the user's home, so a caller could rmtree unrelated
    project data. Only ``DEFAULT_SESSION`` (or a strict descendant) passes
    the whitelist now.
    """
    orch = _orchestrator()
    target = tmp_path / "projects" / "session"
    target.mkdir(parents=True)
    (target / "keepme.txt").write_text("unrelated data", encoding="utf-8")
    with patch("modules.core.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = target
        with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
            orch.delete_session()
    # Nothing was deleted.
    assert (target / "keepme.txt").exists()


def test_orchestrator_refuses_target_when_guard_rejects(tmp_path: Path) -> None:
    """The orchestrator defers to the guard: a rejected target raises.

    Mocked so the cross-platform rule (drive root, near-root, unsafe name)
    lives in the guard and the orchestrator only refuses when told to.
    """
    orch = _orchestrator()
    target = tmp_path / "qwen_session"
    target.mkdir()
    with (
        patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False),
        patch("modules.core.src.agent_session_orchestrator.build_app_config") as build,
        patch(
            "modules.core.src.agent_session_orchestrator.is_safe_session_target",
            return_value=False,
        ) as guard,
    ):
        build.return_value.session_path = target
        with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
            orch.delete_session()
        guard.assert_called_once_with(target.resolve())


def test_delete_session_missing_target_reports_not_found(tmp_path: Path) -> None:
    """A non-existent target is a no-op, not a refusal."""
    orch = _orchestrator()
    with patch("modules.core.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        assert "No session found" in str(orch.delete_session())


def test_delete_session_removes_default_session(tmp_path: Path) -> None:
    """The happy path removes the directory and reports success."""
    orch = _orchestrator()
    fake_default = tmp_path / "share" / "qwen_session"
    fake_default.mkdir(parents=True)
    (fake_default / "Cookies").write_text("token", encoding="utf-8")
    # A retained generation lets the delete go through the normal path instead
    # of hitting the no-backup refusal (#300).
    backups_dir = fake_default / ".backups" / "20250101T000000Z"
    backups_dir.mkdir(parents=True)
    with (
        patch("modules.core.src.utility_core_session_guard.DEFAULT_SESSION", fake_default),
        patch("modules.core.src.agent_session_orchestrator.build_app_config") as build,
    ):
        build.return_value.session_path = fake_default
        result = orch.delete_session()
    assert "deleted successfully" in str(result)
    assert not fake_default.exists()


def test_partial_rmtree_failure_is_reported_with_path(tmp_path: Path) -> None:
    """A failing ``rmtree`` must name the target and flag possible residue."""
    orch = _orchestrator()
    fake_default = tmp_path / "share" / "qwen_session"
    fake_default.mkdir(parents=True)
    # Seed a generation so the no-backup guard does not short-circuit.
    (fake_default / ".backups" / "20250101T000000Z").mkdir(parents=True)
    with (
        patch("modules.core.src.utility_core_session_guard.DEFAULT_SESSION", fake_default),
        patch("modules.core.src.agent_session_orchestrator.build_app_config") as build,
        patch("modules.core.src.agent_session_orchestrator.shutil.rmtree", side_effect=OSError("device busy")),
    ):
        build.return_value.session_path = fake_default
        with pytest.raises(QwenCliError) as excinfo:
            orch.delete_session()
    message = str(excinfo.value)
    assert "device busy" in message
    assert str(fake_default) in message
    assert "partial" in message.lower()
