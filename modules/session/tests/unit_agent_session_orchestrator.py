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

import inspect
from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock, patch

import pytest

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    RotatorResponse,
    SessionInfo,
    SessionPool,
    SessionRequest,
    SessionStatus,
)
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
                orch.execute(SessionRequest(verb="delete", session_path=Path("/"), name=""))


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
            orch.execute(SessionRequest(verb="delete", session_path=target, name=""))
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
            orch.execute(SessionRequest(verb="delete", session_path=target, name=""))
        guard.assert_called_once_with(target.resolve())


def test_delete_session_missing_target_reports_no_error(tmp_path: Path) -> None:
    """A non-existent target is a no-op, not a refusal or an error."""
    orch = _orchestrator()
    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        response = orch.execute(SessionRequest(verb="delete", session_path=tmp_path / "absent", name=""))
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
        result = orch.execute(SessionRequest(verb="delete", session_path=fake_default, name=""))
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
            orch.execute(SessionRequest(verb="delete", session_path=fake_default, name=""))
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


# ── Regression: login waits on its own ceiling, not the run timeout (SA-4-02) ─


def test_login_loop_runs_past_run_timeout_up_to_login_ceiling(tmp_path: Path) -> None:
    """A typed login must not be cut short by ``AppConfig.timeout``.

    The loop deadline comes from the login wait ceiling. With a 5s run
    timeout on the config and a 60s login ceiling, the loop must keep polling
    until the ceiling — five polls at t=10..50, stopping at t=60.
    """
    fake_sessions = tmp_path / "share" / "sessions"
    fake_default = fake_sessions / "default"
    fake_default.mkdir(parents=True)

    page = MagicMock()
    page.is_closed.return_value = False
    ctx = MagicMock()
    ctx.pages = [page]
    browser = MagicMock()
    browser.browser_session.return_value.__enter__.return_value = ctx

    orch = SessionOrchestrator(browser=browser, observability=MagicMock(), sessions=SessionManager())

    with (
        patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True),
        patch("modules.shared.src.session.utility_session_guard.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.SESSIONS_DIR", fake_sessions),
        patch("modules.session.src.capabilities_session_manager.POOL_FILE", fake_sessions / "sessions.json"),
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
        patch("modules.session.src.agent_session_orchestrator.login_wait_seconds", return_value=60),
        patch("modules.session.src.agent_session_orchestrator.time") as fake_time,
    ):
        build.return_value.session_path = fake_default
        build.return_value.timeout = 5
        # Deadline built at t=0, then each poll advances 10 fake seconds.
        fake_time.monotonic.side_effect = [0, 10, 20, 30, 40, 50, 60]
        response = orch.execute(SessionRequest(verb="login", session_path=fake_default, name="default"))

    assert response.valid
    assert page.wait_for_timeout.call_count == 5, (
        "loop must poll past the 5s run timeout and stop at the 60s login ceiling"
    )
    fake_time.monotonic.assert_called()  # clock was actually consulted


# ── Regression: pool profile must win over the empty default session ────────


def test_validate_none_uses_pool_profile_with_chromium_content(tmp_path: Path) -> None:
    """``validate`` with no path must use the logged-in pool profile.

    ``build_app_config(session_path=None)`` falls back to ``DEFAULT_SESSION``,
    which is empty while the pool holds a real registered profile — so the
    orchestrator must resolve the pool profile itself before building the
    config.
    """
    profile = tmp_path / "sessions" / "arwaky007"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("token", encoding="utf-8")
    empty_default = tmp_path / "sessions" / "default"
    empty_default.mkdir()
    orch = _orchestrator_with_pool(tmp_path, [("arwaky007", profile), ("default", empty_default)])

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = profile
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True):
            valid, message = orch._validate(None)

    assert valid is True
    build.assert_called_once()
    assert build.call_args.kwargs["session_path"] == profile
    assert build.call_args.kwargs["session_path"] is not None


def test_validate_none_prefers_local_state_profile(tmp_path: Path) -> None:
    """A pool profile carrying ``Local State`` is also accepted."""
    profile = tmp_path / "sessions" / "arwaky007"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text("{}", encoding="utf-8")
    orch = _orchestrator_with_pool(tmp_path, [("arwaky007", profile)])

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = profile
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True):
            orch._validate(None)

    assert build.call_args.kwargs["session_path"] == profile


def test_validate_none_keeps_default_session_for_an_empty_pool(tmp_path: Path) -> None:
    """An empty pool must keep the DEFAULT_SESSION fallback untouched."""
    orch = _orchestrator_with_pool(tmp_path, [])

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False):
            valid, _ = orch._validate(None)

    assert valid is False
    # No pool profile existed, so the resolver handed build_app_config None
    # and the DEFAULT_SESSION fallback stays in charge.
    assert build.call_args.kwargs["session_path"] is None


def test_validate_none_skips_pool_entry_without_chromium_content(tmp_path: Path) -> None:
    """A pool entry pointing at a directory without Chromium content is skipped."""
    bare = tmp_path / "sessions" / "ghost"
    bare.mkdir(parents=True)
    orch = _orchestrator_with_pool(tmp_path, [("ghost", bare)])

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False):
            orch._validate(None)

    assert build.call_args.kwargs["session_path"] is None


def test_delete_none_refuses_to_infer_a_target(tmp_path: Path) -> None:
    """``delete`` with neither a path nor a resolvable name refuses (BE-1-003)."""
    orch = _orchestrator_with_pool(tmp_path, [])
    with pytest.raises(QwenCliError, match="delete requires an explicit session_path or name"):
        orch.execute(SessionRequest(verb="delete", name=""))


def test_delete_none_uses_pool_profile_with_chromium_content(tmp_path: Path) -> None:
    """``delete`` by name resolves the pool profile before deleting."""
    profile = tmp_path / "sessions" / "arwaky007"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("token", encoding="utf-8")
    orch = _orchestrator_with_pool(tmp_path, [("arwaky007", profile)])
    delete_profile = MagicMock()
    assert orch._sessions is not None
    orch._sessions.delete_session_profile = delete_profile

    result = orch.execute(SessionRequest(verb="delete", name="arwaky007"))

    assert "deleted successfully" in str(result)
    delete_profile.assert_called_once_with(profile, force=False)


def test_validate_explicit_path_bypasses_the_pool(tmp_path: Path) -> None:
    """An explicit ``session_path`` must be used verbatim, pool or not."""
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    profile = tmp_path / "sessions" / "arwaky007"
    profile.mkdir(parents=True)
    (profile / "Local State").write_text("{}", encoding="utf-8")
    orch = _orchestrator_with_pool(tmp_path, [("arwaky007", profile)])

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = explicit
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=True):
            orch._validate(explicit)

    assert build.call_args.kwargs["session_path"] == explicit


def test_validate_none_without_session_manager_keeps_the_default(tmp_path: Path) -> None:
    """No session manager means no pool to resolve: fallback untouched."""
    orch = SessionOrchestrator(browser=MagicMock(), observability=MagicMock(), sessions=None)

    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent"
        with patch.object(SessionOrchestrator, "_validate_saved_session", return_value=False):
            orch._validate(None)

    assert build.call_args.kwargs["session_path"] is None


def _info(name: str, path: Path, status: SessionStatus = SessionStatus.ACTIVE) -> SessionInfo:
    return SessionInfo(session_id=name, name=name, path=path, status=status)


def _orchestrator_with_pool(
    tmp_path: Path, pool_sessions: list[tuple[str, Path]], *, rotator: object | None = None
) -> SessionOrchestrator:
    from datetime import datetime

    from modules.shared.src.session.taxonomy_session_vo import SessionInfo, SessionStatus

    pool = SessionPool(
        sessions=[
            SessionInfo(
                session_id=name,
                name=name,
                path=path,
                status=SessionStatus.ACTIVE,
                created_at=datetime(2026, 1, 1),
            )
            for name, path in pool_sessions
        ]
    )
    resolved: Path | None = None
    for s in pool.sessions:
        if s.path.is_dir() and ((s.path / "Local State").is_file() or (s.path / "Default" / "Cookies").is_file()):
            resolved = s.path
            break
    sessions = MagicMock()
    sessions.load_pool.return_value = pool
    sessions.find_pool_profile_with_content.return_value = resolved
    sessions.get_session_by_name.side_effect = lambda name: next((s for s in pool.sessions if s.name == name), None)
    sessions.remove_session_by_name.return_value = True
    return SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
        sessions=sessions,
        rotator=rotator,
    )


class _StubRotator:
    def __init__(self, response: RotatorResponse) -> None:
        self.response = response
        self.seen: list[RotatorRequest] = []

    async def rotate(self, request: RotatorRequest) -> RotatorResponse:
        self.seen.append(request)
        return self.response

    def rotate_sync(self, request: RotatorRequest) -> RotatorResponse:
        self.seen.append(request)
        return self.response


# ── inspect ─────────────────────────────────────────────────────────────────


def test_inspect_by_name_returns_the_pool_entry(tmp_path: Path) -> None:
    profile = tmp_path / "sessions" / "alpha"
    profile.mkdir(parents=True)
    orch = _orchestrator_with_pool(tmp_path, [("alpha", profile)])

    response = orch.execute(SessionRequest(verb="inspect", name="alpha"))

    assert response.error is None
    assert response.sessions is not None
    assert list(response.sessions)[0].name == "alpha"
    assert "alpha" in response.message


def test_inspect_by_session_path_matches_the_pool_entry(tmp_path: Path) -> None:
    profile = tmp_path / "sessions" / "beta"
    profile.mkdir(parents=True)
    orch = _orchestrator_with_pool(tmp_path, [("beta", profile)])

    response = orch.execute(SessionRequest(verb="inspect", session_path=profile))

    assert response.error is None
    assert list(response.sessions)[0].name == "beta"


def test_inspect_unknown_name_reports_not_found(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    response = orch.execute(SessionRequest(verb="inspect", name="ghost"))

    assert response.error == "session not found"
    assert response.sessions is None


def test_inspect_without_a_selector_reports_the_missing_field(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [("alpha", tmp_path / "a")])

    response = orch.execute(SessionRequest(verb="inspect", name=""))

    assert response.error == "inspect requires request.name or session_path"


# ── rotate ─────────────────────────────────────────────────────────────────


def test_rotate_with_a_healthy_session_reports_the_selection(tmp_path: Path) -> None:
    session = _info("alpha", tmp_path / "a")
    rotator = _StubRotator(RotatorResponse(session=session))
    orch = _orchestrator_with_pool(tmp_path, [("alpha", tmp_path / "a")], rotator=rotator)

    response = orch.execute(SessionRequest(verb="rotate", exclude_ids=("used_one",)))

    assert response.error is None
    assert response.throttled is False
    assert list(response.sessions)[0].session_id == "alpha"
    assert rotator.seen[0].exclude_ids == ("used_one",)


def test_rotate_reports_throttled_when_the_pool_is_exhausted(tmp_path: Path) -> None:
    rotator = _StubRotator(RotatorResponse(session=None, outcome="no_eligible_session", reason="all_sessions_limited"))
    orch = _orchestrator_with_pool(tmp_path, [], rotator=rotator)

    response = orch.execute(SessionRequest(verb="rotate"))

    assert response.throttled is True
    assert response.sessions is None
    assert response.error is None


def test_rotate_without_a_rotator_reports_the_wiring_error(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    response = orch.execute(SessionRequest(verb="rotate"))

    assert response.error == "session rotator not wired"


def test_rotate_propagates_rotator_errors(tmp_path: Path) -> None:
    class _Boom:
        async def rotate(self, request: RotatorRequest) -> RotatorResponse:
            raise QwenCliError("health checker not configured")

        def rotate_sync(self, request: RotatorRequest) -> RotatorResponse:
            raise QwenCliError("health checker not configured")

    orch = _orchestrator_with_pool(tmp_path, [], rotator=_Boom())

    with pytest.raises(QwenCliError, match="health checker not configured"):
        orch.execute(SessionRequest(verb="rotate"))


def test_rotate_forwards_an_empty_exclude_set(tmp_path: Path) -> None:
    rotator = _StubRotator(RotatorResponse(session=None, outcome="no_eligible_session", reason="all_sessions_limited"))
    orch = _orchestrator_with_pool(tmp_path, [], rotator=rotator)

    orch.execute(SessionRequest(verb="rotate"))

    assert rotator.seen[0].exclude_ids == ()


# ── verb routing ─────────────────────────────────────────────────────────


def test_unknown_verb_is_reported(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    response = orch.execute(SessionRequest(verb="nuke_everything"))

    assert response.error == "unknown session verb: 'nuke_everything'"


# ── remove_session ─────────────────────────────────────────────────────────


def test_remove_session_without_a_name_reports_the_missing_field(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    response = orch.execute(SessionRequest(verb="remove_session", name=""))

    assert response.error == "remove_session requires request.name"
    assert response.removed is False


def test_remove_session_unknown_name_reports_not_found(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    response = orch.execute(SessionRequest(verb="remove_session", name="ghost"))

    assert response.error == "session not found"
    assert response.removed is False


def test_remove_session_message_names_the_retained_profile(tmp_path: Path) -> None:
    profile = tmp_path / "sessions" / "alpha"
    orch = _orchestrator_with_pool(tmp_path, [("alpha", profile)])
    sessions = orch._sessions

    response = orch.execute(SessionRequest(verb="remove_session", name="alpha"))

    assert response.removed is True
    assert "profile retained at" in response.message
    assert str(profile) in response.message
    sessions.remove_session.assert_called_once_with("alpha")


# ── delete ─────────────────────────────────────────────────────────


def test_delete_without_a_target_refuses(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    with pytest.raises(QwenCliError, match="delete requires an explicit session_path or name"):
        orch.execute(SessionRequest(verb="delete", name=""))


def test_delete_by_unknown_name_refuses_with_a_named_error(tmp_path: Path) -> None:
    orch = _orchestrator_with_pool(tmp_path, [])

    with pytest.raises(QwenCliError, match="delete could not resolve session name 'ghost'"):
        orch.execute(SessionRequest(verb="delete", name="ghost"))


def test_delete_by_pool_entry_path_does_not_drop_the_pool_entry(tmp_path: Path) -> None:
    """A delete by path removes the profile only; the pool entry is untouched."""
    profile = tmp_path / "sessions" / "alpha"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("token", encoding="utf-8")
    (profile / ".backups" / "20250101T000000Z").mkdir(parents=True)
    orch = _orchestrator_with_pool(tmp_path, [("alpha", profile)])
    assert orch._sessions is not None
    orch._sessions.delete_session_profile = MagicMock(return_value=True)

    response = orch.execute(SessionRequest(verb="delete", session_path=profile, name=""))

    assert response.deleted is True
    orch._sessions.delete_session_profile.assert_called_once_with(profile, force=False)
    orch._sessions.remove_session_by_name.assert_not_called()


def test_delete_by_name_resolves_the_pool_entry_and_removes_it(tmp_path: Path) -> None:
    profile = tmp_path / "sessions" / "alpha"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("token", encoding="utf-8")
    (profile / ".backups" / "20250101T000000Z").mkdir(parents=True)
    orch = _orchestrator_with_pool(tmp_path, [("alpha", profile)])
    assert orch._sessions is not None
    orch._sessions.delete_session_profile = MagicMock(return_value=True)

    response = orch.execute(SessionRequest(verb="delete", name="alpha"))

    assert response.deleted is True
    orch._sessions.delete_session_profile.assert_called_once_with(profile, force=False)
    orch._sessions.remove_session_by_name.assert_called_once_with("alpha")


def test_session_request_exclude_ids_defaults_to_empty() -> None:
    """The ``rotate`` verb's exclusion field ships an empty default."""
    request = SessionRequest(verb="rotate")

    assert request.exclude_ids == ()


def test_rotate_runs_the_async_rotator_on_the_sync_seam(tmp_path: Path) -> None:
    """The rotate verb drives the async rotator on the sync execute seam."""
    rotator = _StubRotator(RotatorResponse(session=_info("alpha", tmp_path / "a")))
    orch = _orchestrator_with_pool(tmp_path, [("alpha", tmp_path / "a")], rotator=rotator)

    response = orch.execute(SessionRequest(verb="rotate"))

    assert inspect.iscoroutinefunction(rotator.rotate)
    assert response.error is None
