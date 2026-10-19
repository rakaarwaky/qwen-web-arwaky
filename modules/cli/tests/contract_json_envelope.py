"""Cross-surface JSON envelope contract test.

One forced failure per ``--json`` surface (jobs, swarm, observability,
doctor) asserts the exact key set ``{success, message, error_code}`` and the
value types, so a surface cannot drift back to an ad-hoc ``error`` payload
without failing this test. The jobs group pins one forced failure per verb
(list / status / cleanup / submit) so the converted branches cannot rot.
The doctor healthy record also pins ``severity != "error"`` for a check
that passed and ``run_doctor == 0`` for a fully healthy fixture.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from modules.cli.src.surface_cli_doctor_command import run_doctor
from modules.cli.src.surface_cli_jobs_command import handle_jobs_command
from modules.cli.src.surface_cli_observability_command import handle_observability_command
from modules.cli.src.surface_cli_swarm_command import handle as handle_swarm_command
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse, SessionStatus
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmResponse

EXPECTED_KEYS = {"success", "message", "error_code"}


def _envelope(capsys) -> dict:
    """Parse the single JSON document a failing --json surface printed."""
    payload = json.loads(capsys.readouterr().out)
    assert set(payload.keys()) == EXPECTED_KEYS, f"envelope keys drifted: {sorted(payload.keys())}"
    assert isinstance(payload["success"], bool)
    assert payload["success"] is False
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["error_code"], str) and payload["error_code"]
    return payload


# ─── jobs: one forced failure per verb ──────────────────────────────────────


def _jobs_args(command: str) -> MagicMock:
    args = MagicMock()
    args.job_command = command
    args.json = True
    args.limit = 10
    args.job_id = "job-missing"
    args.prompt_path = "ignored.md"
    args.attachment_path = None
    args.output_path = None
    args.headless = True
    return args


def test_jobs_validation_failure_is_the_fixed_envelope(tmp_path, capsys) -> None:
    args = _jobs_args("submit")
    args.prompt_path = str(tmp_path / "missing.md")

    assert handle_jobs_command(args, MagicMock()) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"
    assert "missing" in payload["message"].lower()


def test_jobs_list_failure_is_the_fixed_envelope(capsys) -> None:
    args = _jobs_args("list")
    aggregate = MagicMock()
    aggregate.execute.return_value.error = "jobs store unavailable"

    assert handle_jobs_command(args, aggregate) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-500"
    assert "jobs store unavailable" in payload["message"]


def test_jobs_status_missing_record_is_the_fixed_envelope(capsys) -> None:
    args = _jobs_args("status")
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(record=None, error=None)

    assert handle_jobs_command(args, aggregate) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"
    assert "job-missing" in payload["message"]


def test_jobs_cleanup_failure_is_the_fixed_envelope(capsys) -> None:
    args = _jobs_args("cleanup")
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(removed=0, error="cleanup refused")

    assert handle_jobs_command(args, aggregate) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-500"
    assert "cleanup refused" in payload["message"]


@pytest.mark.parametrize(
    "command",
    ["submit", "list", "status", "cleanup"],
)
def test_jobs_failure_stdout_carries_no_cross_mark_or_raw_error_key(command, capsys, tmp_path) -> None:
    """Every jobs verb failure emits the envelope: no ❌, no ``"error":`` key."""
    args = _jobs_args(command)
    args.prompt_path = str(tmp_path / "missing.md")
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(record=None, records=[], removed=0, error="aggregate down")

    assert handle_jobs_command(args, aggregate) == 1
    payload = _envelope(capsys)
    assert not payload["success"]
    assert "error" not in payload


# ─── swarm: unknown swarm id ─────────────────────────────────────────────────


def test_swarm_unknown_id_is_the_fixed_envelope(capsys) -> None:
    args = MagicMock()
    args.swarm_command = "status"
    args.swarm_id = "swarm-does-not-exist"
    args.json = True

    swarm = MagicMock()
    swarm.execute.return_value = SwarmResponse(error=None, snapshot=None)

    assert handle_swarm_command(args, swarm) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"
    assert "swarm-does-not-exist" in payload["message"]


# ─── observability: status file outside the workspace root ─────────────────


def test_observability_failure_is_the_fixed_envelope(tmp_path, capsys, monkeypatch) -> None:
    args = MagicMock()
    args.observability_command = "status"
    args.json = True

    # Point the workspace root at a temporary directory the status file
    # (resolved from DEFAULT_LOG) cannot live inside.
    monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(tmp_path))

    assert handle_observability_command(args, MagicMock()) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"


# ─── doctor: healthy fixture pins the severity sentinel ────────────────────


def _pool_aggregate() -> MagicMock:
    session = MagicMock()
    session.is_healthy = True
    session.is_limited = False
    session.status = SessionStatus.ACTIVE
    session.session_id = "session_1"
    session.name = "default"
    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(
        sessions=SessionList([session]),
        message="1 session(s)",
    )
    return aggregate


def test_doctor_json_healthy_fixture_exits_zero(capsys, monkeypatch, tmp_path) -> None:
    """A fully healthy fixture: all checks pass and the run exits 0.

    The environment is pinned to the passing state (workspace initialized,
    no capacity override) so the severity assertion below cannot hold
    vacuously: a passing check is ``"ok"`` or, for a host limitation such as
    an unavailable OS sandbox, ``"warning"`` — never the failure sentinel
    ``"error"``.
    """
    from modules.shared.src.common.taxonomy_core_constant import LOCAL_WS_DIR

    workspace = tmp_path / LOCAL_WS_DIR
    (workspace / "log").mkdir(parents=True)
    (workspace / "output").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QWEN_WEB_MAX_WORKERS", raising=False)
    monkeypatch.delenv("QWEN_DOCTOR_DEEP", raising=False)
    monkeypatch.delenv("QWEN_DOCTOR_SHOW_PATH", raising=False)
    for name in (
        "QWEN_DISABLE_SANDBOX",
        "QWEN_ENABLE_SANDBOX",
        "ENVIRONMENT",
        "SENTRY_DSN",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)

    assert run_doctor(json_output=True, session=_pool_aggregate()) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "healthy"
    for check in data["checks"]:
        assert check["passed"] is True, f"{check['name']}: expected to pass on the healthy fixture"
        assert check["severity"] != "error", f"{check['name']}: passing check marked 'error'"
        assert check["severity"] in ("ok", "warning"), f"{check['name']}: unknown severity {check['severity']!r}"


def test_doctor_json_sandboxed_pass_is_not_error() -> None:
    """The sandboxed-pass branch and the capacity default pin ``severity != "error"``."""
    from modules.cli.src.surface_cli_doctor_command import _check_capacity, _check_sandbox

    assert _check_sandbox()["severity"] != "error"
    assert _check_capacity()["severity"] != "error"


def test_doctor_json_capacity_override_below_derived_is_not_error() -> None:
    import os
    from unittest.mock import patch

    from modules.cli.src.surface_cli_doctor_command import _check_capacity

    with patch.dict(os.environ, {"QWEN_WEB_MAX_WORKERS": "1"}, clear=False):
        assert _check_capacity()["passed"] is True
        assert _check_capacity()["severity"] == "ok"


def test_doctor_json_capacity_override_above_derived_is_a_warning() -> None:
    """Issue 4: memory oversubscription serializes as a warning, never 'ok'."""
    import os
    from unittest.mock import patch

    from modules.cli.src.surface_cli_doctor_command import _check_capacity, recommended_max_workers

    over = recommended_max_workers() * 10
    with patch.dict(os.environ, {"QWEN_WEB_MAX_WORKERS": str(over)}, clear=False):
        record = _check_capacity()
    assert record["passed"] is True
    assert record["severity"] == "warning"


def test_doctor_empty_pool_json_is_unhealthy(capsys) -> None:
    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(sessions=SessionList([]), message="0 sessions")
    assert run_doctor(json_output=True, session=aggregate) == 1
    data = json.loads(capsys.readouterr().out)
    names = [c["name"] for c in data["checks"]]
    token = data["checks"][names.index("Session Authentication Token")]
    assert token["passed"] is False


# ─── failure channels: stdout JSON, stderr prefix ──────────────────────────


@pytest.mark.parametrize(
    "command,expected_code",
    [
        ("submit", "cli-400"),
        ("list", "cli-500"),
        ("status", "cli-400"),
        ("cleanup", "cli-500"),
    ],
)
def test_jobs_plain_text_failure_carries_the_error_prefix_on_stderr(command, expected_code, tmp_path, capsys) -> None:
    """Without --json the failure is ``[ERROR] …`` on stderr, exit 1."""
    args = _jobs_args(command)
    args.json = False
    args.prompt_path = str(tmp_path / "missing.md")
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(record=None, records=[], removed=0, error="aggregate down")

    assert handle_jobs_command(args, aggregate) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    for line in captured.err.splitlines():
        assert line.startswith("[ERROR]")


# ─── update --rollback: the converted failure branch ───────────────────────


def test_update_rollback_failure_is_the_fixed_envelope(capsys) -> None:
    """The rollback failure path emits the envelope on stdout, not a bare error."""
    from modules.cli.src.surface_cli_update_command import handle_rollback

    args = MagicMock()
    args.rollback = "6.3.0"
    args.json = True
    orchestrator = MagicMock()
    orchestrator.execute.return_value = MagicMock(error="release source unreachable", steps=[])

    assert handle_rollback(args, orchestrator) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-500"


def test_update_rollback_plain_text_failure_carries_the_error_prefix_on_stderr(capsys) -> None:
    """Without --json the rollback failure is ``[ERROR] …`` on stderr."""
    from modules.cli.src.surface_cli_update_command import handle_rollback

    args = MagicMock()
    args.rollback = "6.3.0"
    args.json = False
    orchestrator = MagicMock()
    orchestrator.execute.return_value = MagicMock(error="release source unreachable", steps=[])

    assert handle_rollback(args, orchestrator) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("[ERROR] ")


# ─── session remove: the converted failure branch ──────────────────────────


def test_session_remove_missing_token_is_the_fixed_envelope(capsys) -> None:
    """A remove of an unknown token emits the envelope, never a ``❌`` line."""
    from modules.cli.src.surface_cli_sessions_command import cmd_remove

    args = MagicMock()
    args.session_id = "missing"
    args.keep_profile = False
    args.force = False
    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(valid=True, sessions=SessionList([]))

    assert cmd_remove(aggregate, args, True) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"
