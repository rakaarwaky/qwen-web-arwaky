"""Acceptance tests for FR-UPDATE-003 postflight rollback routing.

These pin the business rule that a postflight check failure routes the same
rollback sequence as a pre-flight or health-gate failure, so a failing
upgrade step and a failing postflight check both end in a restore of the
previous release rather than a half-installed state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modules.shared.src.common.taxonomy_core_vo import UpdateCheckResult, UpdateStepResult
from modules.update.src import capabilities_update_verify as verify_module
from modules.update.src.capabilities_update_verify import UpdateVerifyCapability


def _verify(
    upgrade_ok: bool,
    health_ok: bool,
    *,
    previous: str = "6.4.0",
    latest: str = "6.5.0",
) -> tuple[UpdateVerifyCapability, MagicMock]:
    """Construct a verify capability with the upgrade and health-gate outcomes fixed."""
    check_result = UpdateCheckResult(
        "qwen-web-arwaky",
        previous,
        latest,
        True,
        "github",
    )
    check = MagicMock()
    check.current_version.return_value = previous
    check.check_update.return_value = check_result

    upgrade = MagicMock()
    upgrade.upgrade_package.return_value = UpdateStepResult(
        name="package_upgrade",
        executed=True,
        success=upgrade_ok,
        detail="" if upgrade_ok else "upgrade failed",
    )
    upgrade.sync_browser.return_value = UpdateStepResult(
        name="browser_sync",
        executed=True,
        success=True,
        detail="chromium synced",
    )

    rollback = MagicMock()
    rollback.rollback_to.return_value = (
        UpdateStepResult(name="rollback:package", executed=True, success=True, detail="package restored"),
        UpdateStepResult(name="rollback:browser", executed=True, success=True, detail="browser restored"),
    )

    health = [
        ("health:python_runtime", True, "Python 3.13.0"),
        ("health:package_metadata", True, "installed version resolved: 6.5.0"),
        (
            "health:playwright_chromium",
            health_ok,
            "Chromium binary found" if health_ok else "Chromium binary missing",
        ),
    ]

    capability = UpdateVerifyCapability(
        check,
        upgrade,
        rollback,
        package_name="qwen-web-arwaky",
        smoke_gate=lambda: (health,)[0],
    )
    return capability, rollback


def _patch_version_and_snapshot() -> tuple[patch, patch, patch]:
    """Stub out the version-resolver, chromium check, and snapshot seams."""
    return (
        patch.object(verify_module, "chromium_present", return_value=True),
        patch.object(UpdateVerifyCapability, "_resolve_installed_version", return_value="6.5.0"),
        patch.object(
            UpdateVerifyCapability,
            "_capture_environment_snapshot",
            return_value=UpdateStepResult(
                name="snapshot:environment",
                executed=True,
                success=True,
                detail="pip freeze snapshot written",
            ),
        ),
    )


def test_acceptance_a_postflight_failure_triggers_rollback_same_as_health_gate() -> None:
    """AC: a failing postflight check routes through the same rollback path
    the health gate uses — the sequence of rollback steps is identical."""
    chromium, resolve, snapshot = _patch_version_and_snapshot()
    with chromium, resolve, snapshot:
        cap_health, rollback_health = _verify(upgrade_ok=True, health_ok=False)
        report_health = cap_health.perform_update()

        cap_post, rollback_post = _verify(upgrade_ok=False, health_ok=False)
        report_post = cap_post.perform_update()

    # Both failure modes route through the same rollback path:
    # the rollback is invoked once and with the previous version in both cases.
    rollback_health.rollback_to.assert_called_once_with("6.4.0")
    rollback_post.rollback_to.assert_called_once_with("6.4.0")

    # Both reports mark the run as rolled back.
    assert report_health.rolled_back is True
    assert report_post.rolled_back is True

    # The rollback steps appended to the report are the same sequence
    # (package before browser) in both failure modes.
    health_steps = [s.name for s in report_health.steps if s.name.startswith("rollback:")]
    post_steps = [s.name for s in report_post.steps if s.name.startswith("rollback:")]
    assert health_steps == post_steps == ["rollback:package", "rollback:browser"], (
        "a postflight failure must append the same rollback sequence a health-gate failure uses"
    )

    # Both reports carry a failed health check and an unhealthy outcome.
    assert report_health.healthy is False
    assert report_post.healthy is False
    failed_health = [c for c in report_health.health_checks if not c.success]
    failed_post = [c for c in report_post.health_checks if not c.success]
    assert failed_health, "a failing health-gate check must surface as a failed health check"
    assert failed_post, "a failing postflight check must surface as a failed health check"


def test_acceptance_a_successful_postflight_does_not_rollback() -> None:
    """AC: a postflight check that passes does not trigger the rollback path."""
    chromium, resolve, snapshot = _patch_version_and_snapshot()
    with chromium, resolve, snapshot:
        capability, rollback = _verify(upgrade_ok=True, health_ok=True)
        report = capability.perform_update()

    rollback.rollback_to.assert_not_called()
    assert report.rolled_back is False
    assert report.healthy is True
    assert report.rollback_status == "none"
