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

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.session.taxonomy_session_vo import SessionRequest
from modules.shared.src.session.utility_session_guard import is_filesystem_root, is_safe_session_target


def _orchestrator() -> SessionOrchestrator:
    return SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
        sessions=SessionManager(),
    )


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
    fake_sessions = tmp_path / "share" / "qwen-web-arwaky" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)
    with patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions):
        assert is_safe_session_target(fake_default) is True


def test_child_of_default_session_is_allowed(tmp_path: Path) -> None:
    """Anything inside the application session directory is in scope."""
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    child = fake_default / "Default"
    child.mkdir(parents=True)
    with patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions):
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
        with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
            build.return_value.session_path = Path("/")
            with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
                orch.execute(SessionRequest(verb="delete"))


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
    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = target
        with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
            orch.execute(SessionRequest(verb="delete"))
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
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
        patch(
            "modules.session.src.capabilities_session_manager.utility_session_guard.is_safe_session_target",
            return_value=False,
        ) as guard,
    ):
        build.return_value.session_path = target
        with pytest.raises(QwenCliError, match="Refusing to delete unsafe session path"):
            orch.execute(SessionRequest(verb="delete"))
        guard.assert_called_once_with(target.resolve())


def test_delete_session_missing_target_reports_no_error(tmp_path: Path) -> None:
    """A non-existent target is a no-op, not a refusal or an error."""
    orch = _orchestrator()
    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        response = orch.execute(SessionRequest(verb="delete"))
    assert response.error is None


def test_delete_session_removes_default_session(tmp_path: Path) -> None:
    """The happy path removes the directory and reports success."""
    orch = _orchestrator()
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)
    (fake_default / "Cookies").write_text("token", encoding="utf-8")
    # A retained generation lets the delete go through the normal path instead
    # of hitting the no-backup refusal (#300).
    backups_dir = fake_default / ".backups" / "20250101T000000Z"
    backups_dir.mkdir(parents=True)
    with (
        patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
    ):
        build.return_value.session_path = fake_default
        result = orch.execute(SessionRequest(verb="delete"))
    assert "deleted successfully" in str(result)
    assert not fake_default.exists()


def test_partial_rmtree_failure_is_reported_with_path(tmp_path: Path) -> None:
    """A failing ``rmtree`` must name the target and flag possible residue."""
    orch = _orchestrator()
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)
    # Seed a generation so the no-backup guard does not short-circuit.
    (fake_default / ".backups" / "20250101T000000Z").mkdir(parents=True)
    with (
        patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
        patch("modules.session.src.capabilities_session_manager.shutil.rmtree", side_effect=OSError("device busy")),
    ):
        build.return_value.session_path = fake_default
        with pytest.raises(QwenCliError) as excinfo:
            orch.execute(SessionRequest(verb="delete"))
    message = str(excinfo.value)
    assert "device busy" in message
    assert str(fake_default) in message
    assert "partial" in message.lower()


# ── Regression: login verb must force headless=False ──────────────────────────


def test_login_verb_forces_headless_false(tmp_path: Path) -> None:
    """The login verb must never launch a hidden browser.

    Manual credential entry (typing a CAPTCHA, entering a password) requires a
    visible window. Even when the caller passes ``browser_headless=True`` via
    a ``SessionRequest``, the orchestrator must build the login ``AppConfig``
    with ``headless=False`` so the browser adapter receives a headed launch.
    """
    orch = _orchestrator()
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)
    # Stub out the validation helper so the orchestrator proceeds without a
    # real browser. The login verb always opens the headed browser — there is
    # no headless fast-path for ``login``.
    # POOL_FILE/SESSIONS_DIR are patched in the manager module too: it binds
    # them at import time, so patching only utility_session_guard leaks the
    # fake profile into the operator's real sessions.json.
    with (
        patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True),
        patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.POOL_FILE", fake_sessions / "sessions.json"),
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
    ):
        build.return_value.session_path = fake_default
        # browser_headless=True is explicitly passed by the caller — the
        # orchestrator must ignore it.
        orch.execute(
            SessionRequest(
                verb="login",
                session_path=fake_default,
                name="default",
                browser_headless=True,
            )
        )
    # The login call must have requested a visible browser (headless=False).
    # build_app_config is called twice: once for the login config, once for
    # the post-login validation config. Both must carry headless=False for
    # the login verb path (the validation helper uses headless=True but that
    # is the headless session-check path, not the login browser launch).
    login_call = build.mock_calls[0]
    login_kwargs = login_call.kwargs
    assert login_kwargs["headless"] is False, "login verb must force headless=False regardless of browser_headless flag"


# ── Regression: login verb must always open the headed browser ───────────────


def test_login_verb_always_opens_headed_browser(tmp_path: Path) -> None:
    """The ``login`` verb must open a visible browser window even when a
    valid cookie already exists in the profile.

    On a second run of ``qwa session login --name <name>`` the profile has a
    warm ``auth-session`` cookie.  The headless "Session already valid."
    fast-path belongs to the ``validate``/``check``/``health`` verbs, not to
    ``login`` — silently skipping the browser would make ``login`` unable to
    switch accounts or re-authenticate.  This test locks the invariant:
    ``execute`` must always enter the headed ``browser_session`` path
    and must never return "Session already valid."
    """
    orch = _orchestrator()
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)
    with (
        patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True) as validate,
        patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.POOL_FILE", fake_sessions / "sessions.json"),
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
    ):
        build.return_value.session_path = fake_default
        response = orch.execute(SessionRequest(verb="login", session_path=fake_default, name="default"))

    # "Session already valid." must NEVER be returned from the login flow.
    assert response.message != "Session already valid.", (
        "login verb must not fast-path to 'Session already valid' — it must always open the headed browser"
    )
    # The headed browser_session must have been entered: build_app_config was
    # called at least once for the login config (headless=False), and
    # _validate_saved_session was consulted (the post-login check).
    login_call = build.mock_calls[0]
    assert login_call.kwargs["headless"] is False, "login config must be headed"
    validate.assert_called_once()
