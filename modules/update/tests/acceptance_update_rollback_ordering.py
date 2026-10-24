"""Acceptance tests for the rollback-ordering requirement.

The requirement in `modules/update/FRD.md` FR-UPDATE-004 is that a rollback
restores the install before the browser build, so a half-upgraded state is
never left with the new install and the old browser. These pin the step
order the orchestrator reports and prove that a failed health gate in the
update pipeline restores the install before the browser build.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.shared.src.common.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateStepResult,
    VersionString,
)
from modules.shared.src.update.taxonomy_update_vo import UpdateRequest
from modules.update.src import capabilities_update_rollback as rollback_module
from modules.update.src import capabilities_update_verify as verify_module
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator
from modules.update.src.capabilities_update_rollback import UpdateRollbackCapability
from modules.update.src.capabilities_update_verify import UpdateVerifyCapability


def _step(name: str, success: bool = True, detail: str = "") -> UpdateStepResult:
    return UpdateStepResult(name=name, executed=True, success=success, detail=detail)


def _orchestrator(steps: list[UpdateStepResult]) -> UpdateOrchestrator:
    rollback = MagicMock()
    rollback.rollback_to.return_value = steps
    return UpdateOrchestrator(MagicMock(), MagicMock(), MagicMock(), rollback, observability=MagicMock())


def _failing_health_gate() -> tuple[tuple[str, bool, str], ...]:
    return (("functional_smoke_gate", False, "post-update health gate rejected the release"),)


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


def test_acceptance_a_failed_health_gate_restores_the_install_before_the_browser(tmp_path: Path, monkeypatch) -> None:
    """When the post-update health gate rejects a release, the automatic
    rollback must restore the package install before it re-syncs the browser
    build, leaving no half-upgraded state behind."""
    action_log: list[str] = []

    def record_upgrade(force: ForceFlag = ForceFlag(False), **kwargs: object) -> UpdateStepResult:
        action_log.append("upgrade_package")
        return _step("package_upgrade", detail="installed new release")

    def record_sync_browser(force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        action_log.append("rollback_sync_browser" if bool(force) else "upgrade_sync_browser")
        return _step("browser_sync", detail="reinstalled chromium build")

    def record_install_restore(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        action_log.append("rollback_restore_package")
        return 0, "Successfully installed", ""

    upgrade = MagicMock()
    upgrade.upgrade_package.side_effect = record_upgrade
    upgrade.sync_browser.side_effect = record_sync_browser

    rollback = UpdateRollbackCapability(upgrade, package_name="qwen-web-arwaky")
    check = MagicMock()
    check.current_version.return_value = VersionString("6.4.0")
    check.check_update.return_value = UpdateCheckResult("qwen-web-arwaky", "6.4.0", "6.5.0", True, "github")
    verify = UpdateVerifyCapability(
        check,
        upgrade,
        rollback,
        package_name="qwen-web-arwaky",
        smoke_gate=_failing_health_gate,
    )
    orchestrator = UpdateOrchestrator(
        check,
        upgrade,
        verify,
        rollback,
        observability=MagicMock(),
    )

    state_dir = tmp_path / "state"
    monkeypatch.setattr(verify_module, "XDG_STATE_HOME", state_dir)
    monkeypatch.chdir(tmp_path)

    with (
        patch("modules.shared.src.common.taxonomy_core_constant.XDG_STATE_HOME", state_dir),
        patch.object(rollback_module, "resolve_editable_source_dir", return_value=None),
        patch.object(rollback_module, "resolve_github_pinned_url", return_value="git+https://example.invalid"),
        patch.object(rollback_module, "run_subprocess", side_effect=record_install_restore),
        patch.object(verify_module, "run_subprocess", return_value=(0, "qwen-web-arwaky==6.4.0", "")),
    ):
        response = orchestrator.execute(UpdateRequest(verb="perform_update"))

    assert response.report is not None
    assert response.report.healthy is False, "the health gate must stay failed"
    assert response.report.rolled_back is True, "a failed health gate must trigger the rollback"
    assert response.report.rollback_status == "full"

    step_names = [step.name for step in response.report.steps]
    assert step_names.index("rollback:package") < step_names.index("rollback:browser"), (
        "the recorded rollback steps must restore the install before the browser build"
    )
    rollback_restore_indexes = [i for i, a in enumerate(action_log) if a == "rollback_restore_package"]
    assert rollback_restore_indexes, "the rollback must restore the package install"
    assert "rollback_sync_browser" in action_log, "the rollback must re-sync the browser build"
    assert max(rollback_restore_indexes) < action_log.index("rollback_sync_browser"), (
        "the install must be restored before the browser build, in execution order"
    )
