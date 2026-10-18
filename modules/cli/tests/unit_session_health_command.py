"""Regression test: ``session health`` delegates through the session aggregate.

The CLI surface must not construct capabilities (AES205): ``cmd_health_check``
hands the session aggregate a ``check_health`` request and reports
``response.message`` (plus a nonzero exit when the aggregate answers with an
``error``, e.g. when the health checker seam is not wired). Real browser
probing is owned by the aggregate's capabilities, not this surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.cli.src.surface_cli_sessions_command import cmd_health_check


def _aggregate(*, valid: bool, message: str = "ok", error: str | None = None) -> MagicMock:
    aggregate = MagicMock()
    aggregate.execute.return_value = MagicMock(valid=valid, message=message, error=error)
    return aggregate


def test_cmd_health_check_delegates_check_health_to_the_aggregate() -> None:
    """The health verb reaches the aggregate and exits 0 on a healthy pool."""
    session = _aggregate(valid=True, message="3/3 session(s) healthy")

    assert cmd_health_check(session) == 0

    request = session.execute.call_args.args[0]
    assert request.verb == "check_health"


def test_cmd_health_check_reports_an_unwired_checker_as_failure() -> None:
    """An aggregate answering with an error must exit nonzero, not crash."""
    session = _aggregate(valid=False, message="", error="session health checker not wired")

    assert cmd_health_check(session) == 1


def test_cmd_health_check_survives_an_aggregate_error() -> None:
    """A raising aggregate is reported as a failure, not a crash."""
    session = MagicMock()
    session.execute.side_effect = RuntimeError("browser launch failed")

    assert cmd_health_check(session) == 1
