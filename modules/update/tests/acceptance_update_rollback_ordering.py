"""Acceptance tests for the rollback-ordering requirement.

The requirement in `modules/update/FRD.md` FR-UPDATE-004 is that a rollback
restores the install before the browser build, so a half-upgraded state is
never left with the new install and the old browser. These pin the step
order the orchestrator reports.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.shared.src.taxonomy_core_vo import UpdateStepResult
from modules.shared.src.taxonomy_update_vo import UpdateRequest
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator


def _step(name: str, success: bool = True, detail: str = "") -> UpdateStepResult:
    return UpdateStepResult(name=name, executed=True, success=success, detail=detail)


def _orchestrator(steps: list[UpdateStepResult]) -> UpdateOrchestrator:
    manager = MagicMock()
    manager.rollback_to.return_value = steps
    return UpdateOrchestrator(updater=manager, observability=MagicMock())


def test_acceptance_a_rollback_restores_the_package_before_the_browser() -> None:
    orchestrator = _orchestrator([_step("restore_package"), _step("restore_browser")])

    response = orchestrator.execute(UpdateRequest(verb="rollback_to", previous_version="0.1.0"))

    names = [step.name for step in response.steps]
    assert names.index("restore_package") < names.index("restore_browser"), (
        "the install must be restored before the browser build"
    )


def test_acceptance_a_failed_rollback_step_reports_which_step_stopped() -> None:
    orchestrator = _orchestrator(
        [_step("restore_package"), _step("restore_browser", success=False, detail="binary missing")]
    )

    response = orchestrator.execute(UpdateRequest(verb="rollback_to", previous_version="0.1.0"))

    failed = [step for step in response.steps if not step.success]
    assert failed, "a partially restored install must surface the step that failed"
    assert failed[0].detail == "binary missing"


def test_acceptance_a_rollback_with_no_version_reports_the_reason() -> None:
    orchestrator = _orchestrator([])

    response = orchestrator.execute(UpdateRequest(verb="rollback_to"))

    assert response.error, "a rollback with no target version must name the reason"
