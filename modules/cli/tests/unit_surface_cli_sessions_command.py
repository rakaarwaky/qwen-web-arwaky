"""Unit tests for the session CLI surface (surface_cli_sessions_command).

An in-memory ``ISessionAggregate`` stub stands in for the real pool — no
profile directory is ever touched. Covers the destructive ``remove`` path
(by id, by name, ``--keep-profile``, missing token), the ``--json``
envelope on ``list`` / ``status`` / ``health`` / ``remove``, the login
re-prompt loop with a mocked ``input``, and the terminal-fit table
helpers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from modules.cli.src import surface_cli_sessions_command as sessions
from modules.cli.src.surface_cli_json_hook import _fit, _render_table
from modules.cli.src.surface_cli_sessions_command import (
    _render_pool_table,
    cmd_health_check,
    cmd_list,
    cmd_login,
    cmd_remove,
    cmd_status,
    handle_sessions,
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
    assert aggregate.removes == ["default"]
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
    assert "healthy" in out


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
    aggregate = InMemorySessions()

    def _failing_login(request: SessionRequest) -> SessionResponse:
        return SessionResponse(valid=False, error="login failed")

    aggregate.execute = _failing_login
    args = _args("login", name="work")
    with patch("builtins.input", return_value="n"):
        assert cmd_login(aggregate, args) == 1
    assert "[ERROR]" in capsys.readouterr().err


# ─── handle_sessions dispatch + no-❌ guard ────────────────────────────────


def test_handle_sessions_dispatches_list(capsys) -> None:
    aggregate = InMemorySessions([_info("session_1", "default")])
    args = _args("list")
    assert handle_sessions(args, aggregate) == 0


def test_handle_sessions_without_an_aggregate_fails_cleanly(capsys) -> None:
    args = _args("list", json_output=True)
    assert handle_sessions(args, None) == 1
    out = capsys.readouterr().out
    import json

    payload = json.loads(out)
    assert payload["success"] is False
    assert payload["error_code"] == "cli-500"


def test_no_failure_line_starts_with_a_cross_mark_on_stdout(capsys) -> None:
    """Guard rail: no line beginning with ``❌`` is ever written to stdout."""
    aggregate = InMemorySessions([_info("session_1", "default")])
    handle_sessions(_args("list"), aggregate)
    handle_sessions(_args("status"), aggregate)
    handle_sessions(_args("health"), aggregate)
    out = capsys.readouterr().out
    for line in out.splitlines():
        assert not line.startswith("❌"), f"stdout carried a cross-mark line: {line}"


# ─── terminal-fit table helpers ─────────────────────────────────────────────


def test_fit_truncates_with_an_ellipsis_marker() -> None:
    assert _fit("abcdef", 4) == "abc…"
    assert _fit("ab", 10) == "ab"
    assert _fit("abc", 1) == "…"
    assert _fit("abc", 0) == ""


def test_render_table_fits_to_terminal_size_with_per_column_floors() -> None:
    """Snapshot at COLUMNS=60: wide values get truncated with an ellipsis."""
    rows = (("a" * 30, "b" * 30, "c" * 30), ("short", "med", "very-long-value"))
    text = _render_table(rows, (6, 6, 6), budget=60, rule="-")
    assert text.count("-" * 60) == 2
    # The total content width respects the budget.
    for line in text.splitlines():
        assert len(line) <= 60


def test_render_pool_table_unifies_the_sessions_tables() -> None:
    pool = [_info("session_1", "default", status=SessionStatus.ACTIVE, total_requests=5, failed_requests=0)]
    text = _render_pool_table(pool, sessions._LIST_COLUMNS, sessions._LIST_FLOORS)
    assert "session_1" in text
    assert "default" in text


def test_register_sessions_subparser_exposes_group_json_flag() -> None:
    """The session group registers a --json flag on every subcommand."""

    from modules.root_cli_main_entry import _parse_args

    assert _parse_args(["session", "list", "--json"]).json is True
    assert _parse_args(["session", "status", "--json"]).json is True
    assert _parse_args(["session", "health", "--json"]).json is True
    remove = _parse_args(["session", "remove", "x", "--json", "--keep-profile"])
    assert remove.json is True
    assert remove.keep_profile is True
    assert _parse_args(["session", "list"]).json is False


# ─── module barrel ─────────────────────────────────────────────────────────


def test_module_barrel_lists_all_ten_surfaces() -> None:
    import modules.cli.src as cli_barrel

    expected = [
        "surface_cli_doctor_command",
        "surface_cli_init_command",
        "surface_cli_interactive_controller",
        "surface_cli_jobs_command",
        "surface_cli_observability_command",
        "surface_cli_json_hook",
        "surface_cli_run_command",
        "surface_cli_sessions_command",
        "surface_cli_swarm_command",
        "surface_cli_update_command",
    ]
    assert cli_barrel.__all__ == expected
