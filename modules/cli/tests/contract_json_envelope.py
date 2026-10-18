"""Cross-surface JSON envelope contract test.

One forced failure per ``--json`` surface (jobs, swarm, observability,
doctor) asserts the exact key set ``{success, message, error_code}`` and the
value types, so a surface cannot drift back to an ad-hoc ``error`` payload
without failing this test. The doctor healthy record also pins
``severity != "error"`` for a check that passed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_doctor_command import run_doctor
from modules.cli.src.surface_cli_jobs_command import handle_jobs_command
from modules.cli.src.surface_cli_observability_command import handle_observability_command
from modules.cli.src.surface_cli_swarm_command import handle as handle_swarm_command
from modules.shared.src.common.taxonomy_core_vo import JobRecord
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse, SessionStatus

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


def _job_record() -> JobRecord:
    return JobRecord(
        job_id="job-1",
        created_at="2026-10-10T00:00:00",
        latest_event="DISPATCH_ACKNOWLEDGED",
        completed=False,
        input_file="task.md",
        error=None,
    )


# ─── jobs: bad prompt path ──────────────────────────────────────────────────


def test_jobs_validation_failure_is_the_fixed_envelope(tmp_path, capsys) -> None:
    args = MagicMock()
    args.job_command = "submit"
    args.prompt_path = str(tmp_path / "missing.md")
    args.attachment_path = None
    args.output_path = None
    args.headless = True
    args.json = True

    assert handle_jobs_command(args, MagicMock()) == 1
    payload = _envelope(capsys)
    assert payload["error_code"] == "cli-400"
    assert "missing" in payload["message"].lower()


# ─── swarm: unknown swarm id ─────────────────────────────────────────────────


def test_swarm_unknown_id_is_the_fixed_envelope(capsys) -> None:
    args = MagicMock()
    args.swarm_command = "status"
    args.swarm_id = "swarm-does-not-exist"
    args.json = True

    swarm = MagicMock()
    swarm.execute.return_value = MagicMock(error=None, snapshot=None)

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


def test_doctor_json_healthy_records_never_carry_error_severity(capsys) -> None:
    """A passing check's severity must not be the failure sentinel."""
    assert run_doctor(json_output=True, session=_pool_aggregate()) in (0, 1)
    data = json.loads(capsys.readouterr().out)
    for check in data["checks"]:
        if check["passed"]:
            assert check["severity"] != "error", f"{check['name']}: passing check marked 'error'"


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
        assert _check_capacity()["severity"] != "error"


def test_doctor_empty_pool_json_is_unhealthy(capsys) -> None:
    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(sessions=SessionList([]), message="0 sessions")
    assert run_doctor(json_output=True, session=aggregate) == 1
    data = json.loads(capsys.readouterr().out)
    names = [c["name"] for c in data["checks"]]
    token = data["checks"][names.index("Session Authentication Token")]
    assert token["passed"] is False


# ─── failure channels: stdout JSON, stderr prefix ──────────────────────────


def test_plain_text_failure_carries_the_error_prefix_on_stderr(tmp_path, capsys) -> None:
    """Without --json the failure is ``[ERROR] …`` on stderr, exit 1."""
    args = MagicMock()
    args.job_command = "submit"
    args.prompt_path = str(tmp_path / "missing.md")
    args.attachment_path = None
    args.output_path = None
    args.headless = True
    args.json = False

    assert handle_jobs_command(args, MagicMock()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    for line in captured.err.splitlines():
        assert line.startswith("[ERROR]")
