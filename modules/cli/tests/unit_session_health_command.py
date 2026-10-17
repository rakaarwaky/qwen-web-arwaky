"""Regression test: ``session health`` delegates through the session aggregate.

The CLI surface must not construct capabilities (AES205): ``cmd_health_check``
hands the session aggregate a ``validate`` request and maps ``response.valid``
to the exit code, so a healthy pool exits 0 and an invalid one exits 1. Real
browser probing is owned by the aggregate's capabilities, not this surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.cli.src.surface_cli_sessions_command import cmd_health_check


def _aggregate(*, valid: bool, message: str = "ok") -> MagicMock:
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(valid=valid, message=message)
    return aggregate


def test_cmd_health_check_delegates_validate_to_the_aggregate() -> None:
    """The health verb reaches the aggregate and exits 0 on a valid session."""
    session = _aggregate(valid=True, message="All sessions healthy.")

    assert cmd_health_check(session) == 0

    request = session.execute.call_args.args[0]
    assert request.verb == "validate"


def test_cmd_health_check_reports_an_invalid_pool_as_failure() -> None:
    """An aggregate reporting invalid must exit nonzero, not print a traceback."""
    session = _aggregate(valid=False, message="Session expired. Please log in again.")

    assert cmd_health_check(session) == 1


def test_cmd_health_check_survives_an_aggregate_error() -> None:
    """A raising aggregate is reported as a failure, not a crash."""
    session = MagicMock()
    session.execute.side_effect = RuntimeError("browser launch failed")

    assert cmd_health_check(session) == 1
