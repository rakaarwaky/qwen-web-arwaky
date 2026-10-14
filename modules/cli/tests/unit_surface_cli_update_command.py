"""Unit tests for the update CLI surface and its protocol seams."""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_update_command import handle
from modules.shared.src.common.taxonomy_core_vo import ForceFlag, UpdateCheckResult, UpdateReport


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
    check = MagicMock()
    verify = MagicMock()
    check.check_update.return_value = UpdateCheckResult("qwen-web-arwaky", "6.4.0", "6.5.0", True, "github")
    result = handle(Namespace(check=True, force=False), check, verify)
    assert result["success"] is True
    check.check_update.assert_called_once()
    verify.perform_update.assert_not_called()


def test_update_routes_force_to_verify_protocol() -> None:
    check = MagicMock()
    verify = MagicMock()
    verify.perform_update.return_value = _report(healthy=True)
    result = handle(Namespace(check=False, force=True), check, verify)
    assert result["success"] is True
    verify.perform_update.assert_called_once_with(ForceFlag(True))


def test_failed_update_returns_error_response() -> None:
    check = MagicMock()
    verify = MagicMock()
    verify.perform_update.return_value = _report(healthy=False)
    result = handle(Namespace(check=False, force=False), check, verify)
    assert result["success"] is False
