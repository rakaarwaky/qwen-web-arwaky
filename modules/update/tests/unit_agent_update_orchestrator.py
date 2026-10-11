"""Unit tests for UpdateOrchestrator verb routing across four update protocols."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.shared.src.taxonomy_core_vo import ForceFlag, UpdateCheckResult
from modules.shared.src.taxonomy_update_vo import UpdateRequest
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator


@pytest.fixture
def seams() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return check, upgrade, verify, and rollback protocol stubs."""
    return MagicMock(), MagicMock(), MagicMock(), MagicMock()


def _orchestrator(seams: tuple[MagicMock, MagicMock, MagicMock, MagicMock]) -> UpdateOrchestrator:
    return UpdateOrchestrator(*seams, observability=MagicMock())


def test_check_update_verb_delegates_to_check(seams: tuple[MagicMock, MagicMock, MagicMock, MagicMock]) -> None:
    expected = UpdateCheckResult("qwen-web-arwaky", "6.5.2", "6.6.0", True, "github")
    seams[0].check_update.return_value = expected
    response = _orchestrator(seams).execute(UpdateRequest(verb="check_update"))
    seams[0].check_update.assert_called_once()
    assert response.check_result is expected


def test_perform_update_routes_to_verify(seams: tuple[MagicMock, MagicMock, MagicMock, MagicMock]) -> None:
    _orchestrator(seams).execute(UpdateRequest(verb="perform_update", force=ForceFlag(True)))
    seams[2].perform_update.assert_called_once_with(force=ForceFlag(True))


def test_rollback_routes_to_rollback(seams: tuple[MagicMock, MagicMock, MagicMock, MagicMock]) -> None:
    seams[3].rollback_to.return_value = (MagicMock(),)
    response = _orchestrator(seams).execute(UpdateRequest(verb="rollback_to", previous_version="v6.4.0"))
    seams[3].rollback_to.assert_called_once()
    assert response.steps == seams[3].rollback_to.return_value


def test_rollback_without_version_reports_error(seams: tuple[MagicMock, MagicMock, MagicMock, MagicMock]) -> None:
    response = _orchestrator(seams).execute(UpdateRequest(verb="rollback_to"))
    seams[3].rollback_to.assert_not_called()
    assert response.error is not None
