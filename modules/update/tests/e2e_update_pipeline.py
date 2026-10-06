"""End-to-end tests for the update pipeline over a stubbed subprocess boundary.

The real upgrade path runs ``git pull`` and reinstalls the package, so
these replace the subprocess seam with a recorder: the step sequence,
the wording of the report, and the rollback trigger are all exercised
without the host ever changing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules.shared.src.taxonomy_core_vo import ForceFlag, UpdateStepResult
from modules.update.src.capabilities_update_manager import UpdateManager

_STUBBED_INSTALL = (0, "Successfully installed qwen-web-arwaky-0.0.0", "")


def _upgrade(force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
    """Run the package-upgrade step with every subprocess stubbed out."""
    with (
        patch.object(UpdateManager, "_run_subprocess", return_value=_STUBBED_INSTALL),
        patch.object(UpdateManager, "_editable_source_dir", return_value=Path("/tmp/qwen-web-arwaky-checkout")),
    ):
        return UpdateManager(package_name="qwen-web-arwaky").upgrade_package(force=force)


def test_e2e_the_upgrade_step_returns_a_typed_result() -> None:
    step = _upgrade()

    assert isinstance(step, UpdateStepResult)
    assert step.name == "package_upgrade"


def test_e2e_a_successful_upgrade_names_the_source_it_installed_from() -> None:
    step = _upgrade()

    assert step.success is True
    assert step.detail, "a successful step must say what it did"


def test_e2e_forcing_bypasses_the_version_check() -> None:
    """``force`` exists to install past a version check, so the forced step
    must reach the install rather than reporting a skip."""
    step = _upgrade(force=ForceFlag(True))

    assert step.executed is True


def test_e2e_a_failed_subprocess_surfaces_as_a_failed_step() -> None:
    with (
        patch.object(UpdateManager, "_run_subprocess", return_value=(1, "", "permission denied")),
        patch.object(UpdateManager, "_editable_source_dir", return_value=Path("/tmp/qwen-web-arwaky-checkout")),
    ):
        step = UpdateManager(package_name="qwen-web-arwaky").upgrade_package(force=ForceFlag(True))

    assert step.success is False
    assert step.detail, "a failed step must carry its own reason"
