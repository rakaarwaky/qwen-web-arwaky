"""Smoke tests for the update aggregate.

The aggregate's promise is that both entry runtimes reach the update
pipeline through one door, and that an unknown verb is refused by name.
These drive that door with a stubbed updater, so nothing is installed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.shared.src.update.taxonomy_update_vo import UpdateRequest
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator


def _orchestrator() -> tuple[UpdateOrchestrator, dict[str, MagicMock]]:
    check = MagicMock()
    upgrade = MagicMock()
    verify = MagicMock()
    rollback = MagicMock()
    orchestrator = UpdateOrchestrator(check, upgrade, verify, rollback, observability=MagicMock())
    return orchestrator, {"check": check, "upgrade": upgrade, "verify": verify, "rollback": rollback}


def test_smoke_a_check_routes_to_the_update_capability() -> None:
    orchestrator, seams = _orchestrator()
    orchestrator.execute(UpdateRequest(verb="check_update"))
    seams["check"].check_update.assert_called_once_with()


def test_smoke_a_rollback_requires_a_target_version() -> None:
    orchestrator, _ = _orchestrator()

    response = orchestrator.execute(UpdateRequest(verb="rollback_to"))

    assert response.error, "a rollback with no target must name the reason"
    assert response.steps == ()


def test_smoke_an_unknown_verb_is_refused_by_name() -> None:
    orchestrator, _ = _orchestrator()

    response = orchestrator.execute(UpdateRequest(verb="reinstall_everything"))

    assert response.error is not None
    assert "reinstall_everything" in response.error, "the refusal must name the verb it did not recognize"
