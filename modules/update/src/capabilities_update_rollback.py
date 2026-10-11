"""Capabilities: update FR-UPDATE-004 — restore the previous release in reverse order.

Implements IUpdateRollbackProtocol (contract_update_protocol.py).
Rollback runs only after a FR-UPDATE-003 health-gate failure; it restores the
package before the browser build and reconciles the pre-upgrade dependency
snapshot so the environment matches what the previous version actually ran with.
The shared subprocess sandbox, pinned-release resolution, editable-source
detection, and the browser re-sync live in ``utility_update_pipeline`` and the
injected ``IUpdateUpgradeProtocol`` seam, so this capability never imports a
sibling capability file (AES201).
"""

from __future__ import annotations

import sys
from pathlib import Path

from modules.shared.src.contract_update_protocol import IUpdateRollbackProtocol, IUpdateUpgradeProtocol
from modules.shared.src.taxonomy_core_vo import ForceFlag, UpdateStepResult, VersionString
from modules.shared.src.utility_logger_factory import get_logger
from modules.shared.src.utility_update_pipeline import (
    refuse_unverified_install,
    resolve_editable_source_dir,
    resolve_github_pinned_url,
    run_subprocess,
    tail,
)

log = get_logger("capabilities_update_rollback")


# Block 1: Class Definition & Constructor


class UpdateRollbackCapability(IUpdateRollbackProtocol):
    """FR-UPDATE-004: restore the previous release in reverse order."""

    def __init__(
        self,
        upgrade: IUpdateUpgradeProtocol,
        *,
        package_name: str,
        pip_timeout_sec: float = 600.0,
    ) -> None:
        self.upgrade = upgrade
        self.package_name = package_name
        self.pip_timeout_sec = pip_timeout_sec

    # Block 2: Protocol Method Implementation

    def rollback_to(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Reinstall the previous release and reconcile the pre-upgrade dependency snapshot.

        Restoring package code alone leaves a partial rollback when the failed
        upgrade pulled in newer transitive dependencies, so ``--no-deps`` is
        not used: pip resolves the pinned release's own dependency constraints,
        and a ``pip freeze`` snapshot taken before the upgrade is then
        reconciled so the environment matches what the previous version
        actually ran with (issue #293).
        """
        version = str(previous_version)
        if not version or version == "unknown":
            return (
                UpdateStepResult(
                    "rollback",
                    False,
                    False,
                    "Cannot determine previous version for rollback. Reinstall manually with "
                    f"`pip install {self.package_name}==<previous-version>`.",
                ),
            )
        editable = resolve_editable_source_dir(self.package_name)
        if editable is not None:
            return (
                UpdateStepResult(
                    "rollback",
                    False,
                    False,
                    f"rollback to v{version} is not automated for editable installations; "
                    f"revert the checkout manually: "
                    f"cd {editable} && git checkout v{version} -- . && git pull --ff-only "
                    "(then reconcile dependencies from the snapshot with "
                    f"{self._snapshot_path()})",
                ),
            )
        repo_url = resolve_github_pinned_url(version)
        if repo_url is None:
            step = refuse_unverified_install(version, "rollback")
            return (UpdateStepResult("rollback", step.executed, step.success, step.detail),)
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            "--disable-pip-version-check",
            "--force-reinstall",
            repo_url,
        ]
        try:
            rc, out, err = run_subprocess(cmd, timeout_sec=self.pip_timeout_sec)
            package = UpdateStepResult(
                "rollback:package",
                True,
                rc == 0,
                f"reinstalled {version}" if rc == 0 else tail(err or out),
            )
            if rc != 0:
                return (package,)
            reconcile = self._reconcile_dependency_snapshot()
            steps = [package, *reconcile]
            browser = self.upgrade.sync_browser(ForceFlag(True))
            steps.append(UpdateStepResult("rollback:browser", browser.executed, browser.success, browser.detail))
            return tuple(steps)
        except Exception as exc:
            return (UpdateStepResult("rollback", True, False, str(exc)),)

    # Block 3: Dunder Methods, Factories & Helpers

    def _snapshot_dir(self) -> Path:
        """Return the directory holding pre-upgrade environment snapshots."""
        from modules.shared.src.taxonomy_core_constant import XDG_STATE_HOME

        return XDG_STATE_HOME / "update-snapshots"

    def _snapshot_path(self) -> Path:
        """Return the path of the most recent environment snapshot."""
        return self._snapshot_dir() / "pip-freeze.txt"

    def _reconcile_dependency_snapshot(self) -> tuple[UpdateStepResult, ...]:
        """Reinstall the snapshot's dependency tree so rollback is not partial.

        Runs ``pip install -r <snapshot>`` after the previous package is
        reinstalled, pinning transitive dependencies back to the versions the
        pre-upgrade environment carried (issue #293).
        """
        snapshot = self._snapshot_path()
        if not snapshot.is_file():
            return (
                UpdateStepResult(
                    "rollback:dependencies",
                    False,
                    True,
                    "no pre-upgrade snapshot available; dependencies were resolved from the "
                    "pinned release metadata instead",
                ),
            )
        rc, out, err = run_subprocess(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-input",
                "--disable-pip-version-check",
                "-r",
                str(snapshot),
            ],
            timeout_sec=self.pip_timeout_sec,
        )
        return (
            UpdateStepResult(
                "rollback:dependencies",
                True,
                rc == 0,
                f"reconciled dependencies from {snapshot}"
                if rc == 0
                else f"dependency reconcile failed (rc={rc}): {tail(err or out)}",
            ),
        )

    def __repr__(self) -> str:
        return f"UpdateRollbackCapability(package={self.package_name!r})"


__all__ = ["UpdateRollbackCapability"]
