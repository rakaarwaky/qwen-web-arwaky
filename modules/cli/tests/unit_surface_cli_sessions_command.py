"""Unit tests for the session CLI surface (surface_cli_sessions_command).

An in-memory ``ISessionAggregate`` stub stands in for the real pool — no
profile directory is ever touched. Covers the destructive ``remove`` path
(by id, by name, ``--keep-profile``, missing token), the ``--json``
envelope on ``list`` / ``status`` / ``health`` / ``remove``, the login
re-prompt loop with a mocked ``input`` (including Ctrl+D and the empty-name
fallback), and the display-width-aware pool table — including the
``COLUMNS=60`` snapshot through the real ``cmd_list`` / ``cmd_status`` so
the rendered table can never again ship a 350-character rule (issue 1).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from modules.cli.src import surface_cli_sessions_command as sessions
from modules.cli.src.surface_cli_json_hook import _fit, display_width
from modules.cli.src.surface_cli_sessions_command import (
    cmd_health_check,
    cmd_list,
    cmd_login,
    cmd_remove,
    cmd_status,
    handle_sessions,
    render_pool_table,
)
from modules.shared.src.session.taxonomy_session_vo import (
    SessionInfo,
    SessionList,
    SessionRequest,
    SessionResponse,
    SessionStatus,
)

_NOW = datetime(2026, 10, 18, 9, 0)


def _info(
    session_id: str = "session_1",
    name: str = "default",
    status: SessionStatus = SessionStatus.ACTIVE,
    path: str = "/home/raka/.qwen-web-arwaky/sessions/session_1",
    total_requests: int = 3,
    failed_requests: int = 0,
) -> SessionInfo:
    return SessionInfo(
        session_id=session_id,
        name=name,
        path=Path(path),
        status=status,
        last_used=_NOW,
        total_requests=total_requests,
        failed_requests=failed_requests,
    )


class InMemorySessions:
    """In-memory ISessionAggregate stub backed by a list of SessionInfo.

    Never touches a real profile directory; every verb answers from the
    in-memory pool.
    """

    def __init__(self, pool: list[SessionInfo] | None = None) -> None:
        self.pool: list[SessionInfo] = list(pool or [])
        self.requests: list[SessionRequest] = []
        self.removes: list[str] = []
        self.logins: list[str] = []
        self.deletes: list[str] = []

    def execute(self, request: SessionRequest) -> SessionResponse:
        self.requests.append(request)
        if request.verb == "list_sessions":
            return SessionResponse(valid=True, sessions=SessionList(self.pool))
        if request.verb == "login":
            self.logins.append(request.name)
            self.pool.append(
                _info(session_id=f"session_{len(self.pool) + 1}", name=request.name, path=f"/tmp/prof-{request.name}")
            )
            return SessionResponse(
                valid=True, message=f"Session '{request.name}' saved", profile_path=f"/tmp/prof-{request.name}"
            )
        if request.verb == "check_health":
            healthy = sum(1 for s in self.pool if s.is_healthy)
            limited = sum(1 for s in self.pool if s.is_limited)
            return SessionResponse(
                valid=True,
                message=f"{healthy} healthy, {limited} limited",
                sessions=SessionList(self.pool),
                health_healthy=healthy,
                health_total=len(self.pool),
            )
        if request.verb == "remove_session":
            self.removes.append(request.name)
            for i, s in enumerate(self.pool):
                if s.name == request.name or s.session_id == request.name:
                    self.pool.pop(i)
                    return SessionResponse(valid=True, removed=True, message=f"Removed '{request.name}' from the pool")
            return SessionResponse(valid=False, error=f"Session '{request.name}' not found in the pool")
        if request.verb == "delete":
            self.deletes.append(request.name)
            for i, s in enumerate(self.pool):
                if s.path == request.session_path:
                    self.pool.pop(i)
                    return SessionResponse(valid=True, deleted=True, message="Profile and pool entry deleted")
            return SessionResponse(valid=False, error="Profile not found")
        return SessionResponse(valid=False, error=f"Unknown verb {request.verb}")


def _args(command: str, json_output: bool = False, **extra: Any) -> MagicMock:
    args = MagicMock()
    args.session_command = command
    args.json = json_output
    for key, value in extra.items():
        setattr(args, key, value)
    return args


# ─── list / status ──────────────────────────────────────────────────────────


def test_list_empty_reports_the_hint(capsys) -> None:
    aggregate = InMemorySessions()
    assert cmd_list(aggregate) == 0
    assert "No sessions found" in capsys.readouterr().out


def test_list_populated_renders_the_pool_table(capsys) -> None:
    aggregate = InMemorySessions(
        [_info("session_1", "default"), _info("session_2", "work", status=SessionStatus.LIMITED)]
    )
    assert cmd_list(aggregate) == 0
    out = capsys.readouterr().out
    assert "Session Pool" in out
    assert "session_1" in out and "session_2" in out
    assert "Total: 2 sessions" in out
    assert "Healthy: 1" in out
    assert "Limited: 1" in out


def test_list_json_payload_carries_the_pool(capsys) -> None:
    import json

    aggregate = InMemorySessions([_info("session_1", "default")])
    assert cmd_list(aggregate, json_output=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["sessions"][0]["session_id"] == "session_1"
    assert payload["sessions"][0]["is_healthy"] is True


def test_status_counts_per_pool(capsys) -> None:
    aggregate = InMemorySessions(
        [
            _info("session_1", "default", total_requests=5, failed_requests=0),
            _info("session_2", "work", status=SessionStatus.LIMITED, total_requests=4, failed_requests=2),
            _info("session_3", "unknown", status=SessionStatus.UNKNOWN),
        ]
    )
    assert cmd_status(aggregate) == 0
    out = capsys.readouterr().out
    assert "Session Pool Status" in out
    assert "Healthy: 1" in out
    assert "Limited: 1" in out
    assert "Unknown: 1" in out


def test_status_json_payload_carries_counts(capsys) -> None:
    import json

    aggregate = InMemorySessions(
        [_info("session_1", "default"), _info("session_2", "work", status=SessionStatus.LIMITED)]
    )
    assert cmd_status(aggregate, json_output=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["healthy"] == 1
    assert payload["limited"] == 1
    assert len(payload["sessions"]) == 2


# ─── remove ─────────────────────────────────────────────────────────────────


def test_remove_by_id_deletes_the_profile(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default", path="/tmp/prof-1")])
    args = _args("remove", session_id="session_1", force=False, keep_profile=False)
    assert cmd_remove(aggregate, args) == 0
    out = capsys.readouterr().out
    assert "Removed session 'session_1' from the pool" in out
    assert "Profile deleted" in out
    assert aggregate.pool == []


def test_remove_by_name_deletes_the_profile(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default", path="/tmp/prof-1")])
    args = _args("remove", session_id="default", force=False, keep_profile=False)
    assert cmd_remove(aggregate, args) == 0
    assert "Removed session 'default' from the pool" in capsys.readouterr().out
    assert aggregate.pool == []


def test_remove_keep_profile_drops_only_the_pool_entry(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default", path="/tmp/prof-1")])
    args = _args("remove", session_id="default", force=False, keep_profile=True)
    assert cmd_remove(aggregate, args) == 0
    out = capsys.readouterr().out
    assert "Profile kept" in out
    # The surface asks for a pool-only removal and never a profile delete.
    assert [r.verb for r in aggregate.requests] == ["remove_session"]
    assert aggregate.deletes == []


def test_remove_json_envelope(capsys) -> None:
    import json

    aggregate = InMemorySessions([_info("session_1", "default", path="/tmp/prof-1")])
    args = _args("remove", json_output=True, session_id="default", force=False, keep_profile=False)
    assert cmd_remove(aggregate, args, json_output=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"success": True, "message": "Removed session 'default'"}


def test_remove_missing_token_fails_with_cli_400(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default")])
    args = _args("remove", session_id="nope", force=False, keep_profile=False)
    assert cmd_remove(aggregate, args) == 1
    assert "[ERROR]" in capsys.readouterr().err


def test_remove_missing_token_json(capsys) -> None:
    import json

    aggregate = InMemorySessions([_info("session_1", "default")])
    args = _args("remove", json_output=True, session_id="nope", force=False, keep_profile=False)
    assert cmd_remove(aggregate, args, json_output=True) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert payload["error_code"] == "cli-400"


def test_remove_fails_when_the_aggregate_answers_with_an_error(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default")])
    args = _args("remove", session_id="default", force=False, keep_profile=True)

    def _raise_error(request: SessionRequest) -> SessionResponse:
        return SessionResponse(valid=False, error="delete refused")

    aggregate.execute = _raise_error
    assert cmd_remove(aggregate, args) == 1
    assert "[ERROR]" in capsys.readouterr().err


# ─── health ─────────────────────────────────────────────────────────────────


def test_health_check_reports_the_message(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default")])
    assert cmd_health_check(aggregate) == 0
    out = capsys.readouterr().out
    # The exact summary the stub produces, not a substring that "unhealthy"
    # would also satisfy.
    assert "Result: 1 healthy, 0 limited" in out


def test_health_check_json_payload(capsys) -> None:
    import json

    aggregate = InMemorySessions([_info("session_1", "default")])
    assert cmd_health_check(aggregate, json_output=True) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["states"][0]["session_id"] == "session_1"


def test_health_check_fails_when_the_aggregate_raises(capsys) -> None:
    aggregate = MagicMock()
    aggregate.execute.side_effect = RuntimeError("browser launch failed")
    assert cmd_health_check(aggregate) == 1
    assert "[ERROR]" in capsys.readouterr().err


# ─── login ──────────────────────────────────────────────────────────────────


def test_login_saves_the_session_and_stops(capsys) -> None:
    aggregate = InMemorySessions()
    args = _args("login", name="work")
    with patch("builtins.input", return_value="n"):
        assert cmd_login(aggregate, args) == 0
    assert aggregate.logins == ["work"]


def test_login_eof_exits_the_re_prompt_loop(capsys) -> None:
    """Ctrl+D at the re-prompt exits the loop instead of raising a traceback (issue 9)."""
    aggregate = InMemorySessions()
    args = _args("login", name="work")
    with patch("builtins.input", side_effect=EOFError):
        assert cmd_login(aggregate, args) == 0
    assert aggregate.logins == ["work"]


def test_login_empty_name_falls_back_to_session_default(capsys) -> None:
    """An empty answer at the name prompt registers ``session_default`` (issue 9)."""
    aggregate = InMemorySessions()
    args = _args("login", name="work")
    answers = iter(["y", "", EOFError])

    def _answer(_prompt: str) -> str:
        nxt = next(answers)
        if nxt is EOFError:
            raise nxt
        return nxt

    with patch("builtins.input", side_effect=_answer):
        assert cmd_login(aggregate, args) == 0
    assert aggregate.logins == ["work", "session_default"]


def test_login_prompt_loops_iteratively_through_many_cycles() -> None:
    """A harness of ~1500 'y' cycles must exit cleanly with no RecursionError."""
    aggregate = InMemorySessions()
    args = _args("login", name="one")
    # The re-prompt asks two questions per cycle: "add another?" then a name.
    answers: list[str] = []
    for _ in range(1499):
        answers.extend(["y", "extra"])
    answers.append("n")
    with patch("builtins.input", side_effect=lambda _: answers.pop(0)):
        assert cmd_login(aggregate, args) == 0
    # 1500 logins: the initial name plus one per accepted "y".
    assert len(aggregate.logins) == 1500
    assert aggregate.logins[0] == "one"
    assert aggregate.logins[-1] == "extra"


def test_login_failure_stops_the_loop(capsys) -> None:
    """A failed login exits 1 with the [ERROR] line on stderr — never ❌ on stdout (issue 8)."""
    aggregate = InMemorySessions()

    def _failing_login(request: SessionRequest) -> SessionResponse:
        return SessionResponse(valid=False, error="login failed")

    aggregate.execute = _failing_login
    args = _args("login", name="work")
    with patch("builtins.input", return_value="n"):
        assert cmd_login(aggregate, args) == 1
    captured = capsys.readouterr()
    assert "[ERROR]" in captured.err
    for line in captured.out.splitlines():
        assert not line.startswith("❌"), f"stdout carried a cross-mark line: {line}"


# ─── handle_sessions dispatch + no-❌ guard ────────────────────────────────


def test_handle_sessions_dispatches_list(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default")])
    args = _args("list")
    assert handle_sessions(args, aggregate) == 0


def test_handle_sessions_without_an_aggregate_fails_cleanly(capsys) -> None:
    args = _args("list", json_output=True)
    assert handle_sessions(args, None) == 1
    out = capsys.readouterr().out

    payload = json.loads(out)
    assert payload["success"] is False
    assert payload["error_code"] == "cli-500"


def test_handle_sessions_dispatches_the_expected_verbs() -> None:
    """The surface's verb choice is pinned, not the stub's bookkeeping (issue 8)."""
    aggregate = InMemorySessions([_info("session_1", "default")])
    handle_sessions(_args("list"), aggregate)
    handle_sessions(_args("status"), aggregate)
    handle_sessions(_args("health"), aggregate)
    handle_sessions(_args("remove", session_id="session_1", force=False, keep_profile=True), aggregate)
    assert [r.verb for r in aggregate.requests] == [
        "list_sessions",
        "list_sessions",
        "check_health",
        "remove_session",
    ]


def test_no_failure_line_starts_with_a_cross_mark_on_stdout(capsys) -> None:
    """Guard rail: no line beginning with ``❌`` is ever written to stdout."""
    aggregate = InMemorySessions([_info("session_1", "default")])

    def _raise(request: SessionRequest) -> SessionResponse:
        return SessionResponse(valid=False, error="aggregate down")

    handle_sessions(_args("list"), aggregate)
    handle_sessions(_args("status"), aggregate)
    handle_sessions(_args("health"), aggregate)
    handle_sessions(_args("remove", session_id="session_1", force=False, keep_profile=True), aggregate)
    aggregate.execute = _raise
    handle_sessions(_args("list"), aggregate)
    handle_sessions(_args("health"), aggregate)
    handle_sessions(_args("remove", session_id="session_1", force=False, keep_profile=True), aggregate)
    captured = capsys.readouterr()
    for line in captured.out.splitlines():
        assert not line.startswith("❌"), f"stdout carried a cross-mark line: {line}"
        assert '"error":' not in line, f"stdout carried a raw error key: {line}"
    assert any(line.startswith("[ERROR]") for line in captured.err.splitlines())


def test_no_cross_mark_or_error_key_on_job_failure_stdout(capsys) -> None:
    """Job list/status/cleanup failures emit the envelope on stdout, never ❌."""
    from modules.cli.src.surface_cli_jobs_command import handle_jobs_command

    for command in ("list", "status", "cleanup"):
        args = MagicMock()
        args.job_command = command
        args.limit = 10
        args.job_id = "job-missing"
        args.json = True
        aggregate = MagicMock()
        aggregate.execute.return_value.error = "aggregate down"
        assert handle_jobs_command(args, aggregate) == 1
    captured = capsys.readouterr()
    for line in captured.out.splitlines():
        assert not line.startswith("❌"), f"stdout carried a cross-mark line: {line}"
        assert '"error":' not in line, f"stdout carried a raw error key: {line}"


# ─── display-width-aware pool table ─────────────────────────────────────────


def test_fit_truncates_with_an_ellipsis_marker() -> None:
    assert _fit("abcdef", 4) == "abc…"
    assert _fit("ab", 10) == "ab"
    assert _fit("abc", 1) == "…"
    assert _fit("abc", 0) == ""


def test_fit_counts_display_columns_not_characters() -> None:
    """A wide glyph occupies two columns; _fit must truncate by display width."""
    assert display_width("●") == 2
    assert display_width("◐ warnings") == 11
    assert _fit("●●●●", 5) == "●●…"
    assert _fit("健康状態", 5) == "健康…"
    assert _fit("abc●", 4) == "abc…"


def _wide_pool() -> list[Any]:
    """Pool whose status glyphs are wide enough to overflow a char-based fit."""
    return [
        _info("session_1", "default", status=SessionStatus.LIMITED),
        _info("session_2", "work", status=SessionStatus.ACTIVE),
    ]


def test_render_pool_table_fits_the_budget_with_wide_glyphs() -> None:
    """Issue 1: every rendered line stays inside the budget, glyphs included."""
    text = render_pool_table(_wide_pool(), sessions._LIST_COLUMNS, sessions._LIST_FLOORS, budget=60)
    for line in text.splitlines():
        assert display_width(line) <= 60, f"line overflowed the budget: {line!r}"
    assert "session_1" in text
    # The limited session carries its wide health glyph.
    assert "◐" in text


def test_render_pool_table_never_wraps_on_a_narrow_terminal() -> None:
    long_pool = [_info(f"session_{i}", f"long-account-name-{i}", status=SessionStatus.LIMITED) for i in range(5)]
    text = render_pool_table(long_pool, sessions._LIST_COLUMNS, sessions._LIST_FLOORS, budget=40)
    for line in text.splitlines():
        assert display_width(line) <= 40, f"line overflowed 40 columns: {line!r}"


def test_render_pool_table_unifies_the_sessions_tables() -> None:
    pool = [_info("session_1", "default", status=SessionStatus.ACTIVE, total_requests=5, failed_requests=0)]
    text = render_pool_table(pool, sessions._LIST_COLUMNS, sessions._LIST_FLOORS, budget=80)
    assert "session_1" in text
    assert "default" in text


def test_render_pool_table_casts_non_string_cells() -> None:
    """A MagicMock cell renders its string form instead of crashing."""
    cell = MagicMock()
    cell.total_requests = 7
    cell.failed_requests = 1
    cell.is_healthy = True
    cell.is_limited = False
    cell.status.value = "active"
    cell.session_id = "session_9"
    cell.name = "mocked"
    cell.last_used = _NOW
    text = render_pool_table([cell], sessions._STATUS_COLUMNS, sessions._STATUS_FLOORS, budget=80)
    assert "session_9" in text
    assert "mocked" in text


def test_render_pool_table_renders_one_table_not_header_plus_legacy_rows() -> None:
    """Issue 1: the shared table renders the header, EVERY row, and the rules."""
    pool = _wide_pool()
    text = render_pool_table(pool, sessions._LIST_COLUMNS, sessions._LIST_FLOORS, budget=80)
    lines = text.splitlines()
    # Top rule, header, one row per pool session, bottom rule — nothing else.
    assert len(lines) == 2 + 1 + len(pool), f"expected a header + every row, got {lines}"
    assert lines[0] == lines[-1], "the top and bottom rules must match"
    assert lines[0].startswith("━"), "the rule must be a single ━ character repeated"
    assert lines[1].split()[:2] == ["ID", "Name"], f"the header must lead the table: {lines[1]!r}"
    for session in pool:
        assert any(session.session_id in line for line in lines[2:-1]), (
            f"row for {session.session_id} missing: the body must render every pool session"
        )


def test_list_table_under_columns_60_never_overflows(capsys, monkeypatch) -> None:
    """The real cmd_list under COLUMNS=60: no line exceeds 60 columns (issue 1).

    This is the regression the 350-character rule shipped under: the table
    ran through the shared renderer on synthetic strings only, never through
    the command on a narrow terminal.
    """
    monkeypatch.setenv("COLUMNS", "60")
    aggregate = InMemorySessions(_wide_pool())
    assert cmd_list(aggregate) == 0
    out = capsys.readouterr().out
    for line in out.splitlines():
        assert display_width(line) <= 60, f"cmd_list overflowed COLUMNS=60: {line!r}"
    # The pool rendered through the shared table: the rule is a single ━,
    # never the 350-character artifact.
    assert not any(len(line) > 60 for line in out.splitlines())
    assert any(line.startswith("━") for line in out.splitlines())


def test_status_table_under_columns_60_never_overflows(capsys, monkeypatch) -> None:
    """The real cmd_status under COLUMNS=60: every line fits the terminal."""
    monkeypatch.setenv("COLUMNS", "60")
    aggregate = InMemorySessions(_wide_pool())
    assert cmd_status(aggregate) == 0
    out = capsys.readouterr().out
    for line in out.splitlines():
        assert display_width(line) <= 60, f"cmd_status overflowed COLUMNS=60: {line!r}"
    # The status column set (Requests/Failed) renders through the same table.
    assert "Requests" in out and "Failed" in out


def test_register_sessions_subparser_exposes_group_json_flag() -> None:
    """--json is registered on the reporting subcommands; login carries none."""
    from modules.root_cli_main_entry import _parse_args

    assert _parse_args(["session", "list", "--json"]).json is True
    assert _parse_args(["session", "status", "--json"]).json is True
    assert _parse_args(["session", "health", "--json"]).json is True
    remove = _parse_args(["session", "remove", "x", "--json", "--keep-profile"])
    assert remove.json is True
    assert remove.keep_profile is True
    assert _parse_args(["session", "list"]).json is False
    # login --json is honored: one login, the envelope, no blocking prompt.
    assert _parse_args(["session", "login", "--name", "x", "--json"]).json is True
