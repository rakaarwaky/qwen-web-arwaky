"""Unit tests for UpdateOrchestrator: pipeline delegation and rollback."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.core.src.agent_update_orchestrator import UpdateOrchestrator


@pytest.fixture
def stub() -> MagicMock:
    """A protocol-compliant stub updater that never touches the environment."""
    return MagicMock()


def test_updater_is_held_verbatim() -> None:
    """The injected updater is the one every call goes through."""
    stub = MagicMock()
    orchestrator = UpdateOrchestrator(updater=stub)
    assert orchestrator._updater is stub


def test_check_delegates_to_updater() -> None:
    stub = MagicMock()
    UpdateOrchestrator(updater=stub).check()
    stub.check_update.assert_called_once()


def test_perform_delegates_with_force() -> None:
    stub = MagicMock()
    UpdateOrchestrator(updater=stub).perform(force=True)
    stub.perform_update.assert_called_once()


def test_perform_defaults_to_no_force() -> None:
    stub = MagicMock()
    UpdateOrchestrator(updater=stub).perform()
    stub.perform_update.assert_called_once()
    assert stub.perform_update.call_args.kwargs["force"] is not True


def test_rollback_delegates_to_updater() -> None:
    step = MagicMock()
    stub = MagicMock()
    stub.rollback_to.return_value = (step, MagicMock())
    result = UpdateOrchestrator(updater=stub).rollback("v6.4.0")
    stub.rollback_to.assert_called_once_with("v6.4.0")
    assert result == (step, stub.rollback_to.return_value[1])
