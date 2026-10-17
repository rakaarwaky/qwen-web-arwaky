"""Unit tests for the update CLI surface and its protocol seams."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_update_command import handle
from modules.shared.src.common.taxonomy_core_vo import ForceFlag, UpdateCheckResult, UpdateReport
from modules.shared.src.update.taxonomy_update_vo import UpdateResponse


def _report(*, healthy: bool) -> UpdateReport:
    return UpdateReport(
        package_name="qwen-web-arwaky",
        previous_version="6.4.0",
        latest_version="6.5.0",
        source="github",
        update_available=True,
        forced=False,
        changed=healthy,
        steps=(),
        health_checks=(),
        post_update_version="6.5.0" if healthy else "6.4.0",
        healthy=healthy,
        message="ok" if healthy else "failed",
    )


def test_check_uses_only_check_protocol() -> None:
    orchestrator = MagicMock()
    orchestrator.execute.return_value = UpdateResponse(
        check_result=UpdateCheckResult("qwen-web-arwaky", "6.4.0", "6.5.0", True, "github")
    )
    result = handle(Namespace(check=True, force=False), orchestrator)
    assert result["success"] is True
    verbs = [c.args[0].verb for c in orchestrator.execute.call_args_list]
    assert verbs == ["check_update"]


def test_update_routes_force_to_verify_protocol() -> None:
    orchestrator = MagicMock()
    orchestrator.execute.return_value = UpdateResponse(report=_report(healthy=True))
    result = handle(Namespace(check=False, force=True), orchestrator)
    assert result["success"] is True
    request = orchestrator.execute.call_args.args[0]
    assert request.verb == "perform_update"
    assert request.force == ForceFlag(True)


def test_failed_update_returns_error_response() -> None:
    orchestrator = MagicMock()
    orchestrator.execute.return_value = UpdateResponse(report=_report(healthy=False))
    result = handle(Namespace(check=False, force=False), orchestrator)
    assert result["success"] is False
