"""Integration tests for doctor --smoke wiring (issue #322).

Locks the deterministic part of the smoke path: the CLI flag reaches
run_doctor, the injected session aggregate is called exactly once, and the
sixth check's pass/fail follows the aggregate result. The live browser
round-trip itself needs an authenticated session, so it stays operator-run.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_doctor_command import run_doctor
from modules.root_cli_main_entry import _parse_args


def test_parse_args_accepts_smoke_flag() -> None:
    """`doctor --smoke` must parse; the default is off."""
    assert getattr(_parse_args(["doctor", "--smoke"]), "smoke", False) is True
    assert getattr(_parse_args(["doctor"]), "smoke", False) is False


def test_smoke_appends_sixth_check_and_maps_result(capsys) -> None:
    """A valid session yields a sixth passing check (issue #322 acceptance)."""
    session = MagicMock()
    session.validate_session.return_value = (True, "Saved Qwen session is valid and ready to use.")

    run_doctor(json_output=True, smoke=True, session=session)
    session.validate_session.assert_called_once()

    data = json.loads(capsys.readouterr().out)
    names = [check["name"] for check in data["checks"]]
    assert "Browser Smoke Test" in names
    assert data["checks"][names.index("Browser Smoke Test")]["passed"] is True


def test_smoke_failure_flags_check_unhealthy(capsys) -> None:
    """An invalid session marks the check failed and the run unhealthy."""
    session = MagicMock()
    session.validate_session.return_value = (False, "Saved Qwen session is invalid or expired. Please log in again.")

    assert run_doctor(json_output=True, smoke=True, session=session) == 1

    data = json.loads(capsys.readouterr().out)
    names = [check["name"] for check in data["checks"]]
    smoke = data["checks"][names.index("Browser Smoke Test")]
    assert smoke["passed"] is False
    assert "invalid or expired" in smoke["detail"]
    assert data["status"] == "unhealthy"


def test_smoke_aggregate_exception_reports_failure(capsys) -> None:
    """A launch failure is reported as a failed check, not a traceback."""
    session = MagicMock()
    session.validate_session.side_effect = RuntimeError("browser launch exploded")

    assert run_doctor(json_output=True, smoke=True, session=session) == 1

    data = json.loads(capsys.readouterr().out)
    names = [check["name"] for check in data["checks"]]
    smoke = data["checks"][names.index("Browser Smoke Test")]
    assert smoke["passed"] is False
    assert "browser launch exploded" in smoke["detail"]


def test_smoke_without_session_injection_fails_cleanly(capsys) -> None:
    """Calling the surface directly without an aggregate must not crash."""
    run_doctor(json_output=True, smoke=True, session=None)

    data = json.loads(capsys.readouterr().out)
    names = [check["name"] for check in data["checks"]]
    assert data["checks"][names.index("Browser Smoke Test")]["passed"] is False


def test_smoke_disabled_keeps_five_checks(capsys) -> None:
    """Without --smoke the classic 5-check report is unchanged (regression lock)."""
    session = MagicMock()
    run_doctor(json_output=True, smoke=False, session=session)
    session.validate_session.assert_not_called()
    assert len(json.loads(capsys.readouterr().out)["checks"]) == 5


def test_root_dispatch_passes_session_aggregate() -> None:
    """Root _dispatch wires the container's session aggregate into run_doctor."""
    import modules.root_cli_main_entry as root_entry

    container = MagicMock()
    args = _parse_args(["doctor", "--smoke", "--json"])

    with patch("modules.cli.src.surface_cli_doctor_command.run_doctor", return_value=0) as mock_doctor:
        assert root_entry._dispatch(container, ["doctor", "--smoke"], args, None) == 0

    mock_doctor.assert_called_once()
    assert mock_doctor.call_args.kwargs["session"] is container.agent_session_orchestrator
