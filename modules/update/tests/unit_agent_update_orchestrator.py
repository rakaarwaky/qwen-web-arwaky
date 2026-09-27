"""Unit tests for UpdateOrchestrator: verb routing over the update capability."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.shared.src.taxonomy_core_vo import UpdateCheckResult
from modules.shared.src.taxonomy_update_vo import ForceFlag, UpdateRequest
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator


@pytest.fixture
def stub() -> MagicMock:
    """A protocol-compliant stub updater that never touches the environment."""
    return MagicMock()


def test_updater_is_held_verbatim() -> None:
    """The injected updater is the one every call goes through."""
    stub = MagicMock()
    orchestrator = UpdateOrchestrator(updater=stub)
    assert orchestrator._updater is stub


def test_check_update_verb_delegates_to_updater() -> None:
    """The check_update verb reaches check_update() and returns its result."""
    expected = UpdateCheckResult(
        package_name="qwen-web-arwaky",
        current_version="6.5.2",
        latest_version="6.6.0",
        update_available=True,
        source="github",
    )
    stub = MagicMock()
    stub.check_update.return_value = expected

    response = UpdateOrchestrator(updater=stub).execute(UpdateRequest(verb="check_update"))

    stub.check_update.assert_called_once()
    assert response.check_result is expected
    assert response.error is None


def test_perform_update_verb_delegates_with_force() -> None:
    """The perform_update verb carries the force flag through to the capability."""
    stub = MagicMock()
    UpdateOrchestrator(updater=stub).execute(
        UpdateRequest(verb="perform_update", force=ForceFlag(True)),
    )
    stub.perform_update.assert_called_once_with(force=ForceFlag(True))


def test_perform_update_verb_defaults_to_no_force() -> None:
    """An unset force flag reaches the capability as ForceFlag(False)."""
    stub = MagicMock()
    UpdateOrchestrator(updater=stub).execute(UpdateRequest(verb="perform_update"))
    stub.perform_update.assert_called_once_with(force=ForceFlag(False))


def test_rollback_to_verb_delegates_to_updater() -> None:
    """The rollback_to verb passes the version on and returns the ordered steps."""
    step = MagicMock()
    stub = MagicMock()
    stub.rollback_to.return_value = (step, MagicMock())

    response = UpdateOrchestrator(updater=stub).execute(
        UpdateRequest(verb="rollback_to", previous_version="v6.4.0"),
    )

    stub.rollback_to.assert_called_once()
    assert response.steps == stub.rollback_to.return_value


def test_rollback_without_version_reports_error() -> None:
    """A rollback verb with no version names the reason instead of calling the capability."""
    stub = MagicMock()
    response = UpdateOrchestrator(updater=stub).execute(UpdateRequest(verb="rollback_to"))
    stub.rollback_to.assert_not_called()
    assert response.error is not None
    assert response.steps == ()
