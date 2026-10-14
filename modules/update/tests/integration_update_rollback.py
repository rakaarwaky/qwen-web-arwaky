"""Integration tests for the update rollback against the real install.

These drive ``rollback_to`` on this checkout, which is an editable
install, so the rollback must refuse with instructions rather than reach
for pip or the network.
"""

from __future__ import annotations

from modules.shared.src.common.taxonomy_core_vo import UpdateStepResult, VersionString
from modules.update.src.capabilities_update_rollback import UpdateRollbackCapability
from modules.update.src.capabilities_update_upgrade import UpdateUpgradeCapability


def _manager() -> UpdateRollbackCapability:
    upgrade = UpdateUpgradeCapability()
    return UpdateRollbackCapability(upgrade, package_name="qwen-web-arwaky")


def test_integration_a_rollback_reports_a_typed_step_per_outcome() -> None:
    steps = _manager().rollback_to(VersionString("0.0.0"))

    assert steps, "a rollback must report what it did, even when it refused"
    assert all(isinstance(step, UpdateStepResult) for step in steps)


def test_integration_an_editable_install_refuses_the_automated_rollback() -> None:
    """Reinstalling a pinned release over an editable checkout would replace
    the developer's own working tree, so the refusal is the safe answer."""
    steps = _manager().rollback_to(VersionString("0.0.0"))

    assert not all(step.success for step in steps), (
        "an editable install must not report an automated rollback as successful"
    )


def test_integration_a_refused_rollback_names_the_manual_recovery() -> None:
    steps = _manager().rollback_to(VersionString("0.0.0"))

    refused = [step for step in steps if not step.success]
    assert refused
    assert refused[0].detail, "a refusal must tell the operator how to recover by hand"


def test_integration_an_unknown_previous_version_names_the_reason() -> None:
    steps = _manager().rollback_to(VersionString("unknown"))

    assert len(steps) == 1
    assert steps[0].success is False
    assert steps[0].detail, "a rollback with no resolvable target must name the reason"
