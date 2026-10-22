"""Capabilities: update FR-UPDATE-003 — full pipeline run and post-update gate.

Implements IUpdateVerifyProtocol (contract_update_protocol.py).
Owns the environment snapshot, the post-flight health checks, the injected
functional smoke gate, and the rollback decision (run the gate, then restore
the previous version when it fails) so no caller can skip it.

The other three capabilities arrive as protocol seams (``IUpdateCheckProtocol``,
``IUpdateUpgradeProtocol``, ``IUpdateRollbackProtocol``); the low-level shared
mechanics (subprocess sandbox, Chromium checks, version resolution, dependency
snapshot) live in the focused update utility modules so this capability never imports
a sibling capability file (AES201).
"""

from __future__ import annotations

import contextlib
import importlib
import json
import sys
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import XDG_STATE_HOME
from modules.shared.src.common.taxonomy_core_vo import ForceFlag, UpdateReport, UpdateStepResult, VersionString
from modules.shared.src.common.utility_core_version import get_package_version
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.update.contract_update_protocol import (
    ISmokeGate,
    IUpdateCheckProtocol,
    IUpdateRollbackProtocol,
    IUpdateUpgradeProtocol,
    IUpdateVerifyProtocol,
)
from modules.shared.src.update.utility_update_chromium import chromium_present, playwright_browsers_path
from modules.shared.src.update.utility_update_refusal import smoke_gate_unavailable
from modules.shared.src.update.utility_update_subprocess import run_pip_show, run_subprocess, tail
from modules.shared.src.update.utility_update_version import compare_versions

log = get_logger("capabilities_update_verify")


# Block 1: Class Definition & Constructor


class UpdateVerifyCapability(IUpdateVerifyProtocol):
    """FR-UPDATE-003: run the full pipeline and verify the post-update state."""

    def __init__(
        self,
        check: IUpdateCheckProtocol,
        upgrade: IUpdateUpgradeProtocol,
        rollback: IUpdateRollbackProtocol,
        *,
        package_name: str,
        smoke_gate: ISmokeGate | None = None,
    ) -> None:
        self.check = check
        self.upgrade = upgrade
        self.rollback = rollback
        self.package_name = package_name
        self._smoke_gate = smoke_gate or (lambda: ())

    # Block 2: Protocol Method Implementation

    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report."""
        forced = bool(force)
        previous = self.check.current_version()
        check = self.check.check_update()
        if check.latest_version is None:
            message = "Update refused: cannot verify target version; no package changes were made."
            log.error("update_refused_unverifiable_target source=%s error=%s", check.source, check.error)
            return UpdateReport(
                package_name=self.package_name,
                previous_version=str(previous),
                latest_version=None,
                source=check.source,
                update_available=False,
                forced=forced,
                changed=False,
                steps=(),
                health_checks=(),
                post_update_version=str(previous),
                healthy=False,
                message=message,
            )
        up_to_date = check.latest_version is not None and str(previous) != "unknown" and not check.update_available
        if up_to_date and not forced and chromium_present():
            message = (
                f"{self.package_name} {previous} is already up to date "
                f"(latest {check.latest_version} via {check.source}); Chromium present. "
                "Use --force to reinstall anyway."
            )
            log.info("update_skipped_up_to_date version=%s", previous)
            return UpdateReport(
                package_name=self.package_name,
                previous_version=str(previous),
                latest_version=check.latest_version,
                source=check.source,
                update_available=False,
                forced=False,
                changed=False,
                steps=(),
                health_checks=(),
                post_update_version=str(previous),
                healthy=True,
                message=message,
            )
        steps: list[UpdateStepResult] = []
        # Capture the current environment so a rollback can reconcile more than
        # just the package code (issue #293). The snapshot lives under the XDG
        # state dir and is named after the release being left.
        snapshot = self._capture_environment_snapshot(previous)
        steps.append(snapshot)
        pkg_step = self.upgrade.upgrade_package(ForceFlag(forced), target_version=check.latest_version)
        steps.append(pkg_step)
        importlib.invalidate_caches()
        browser_step = self.upgrade.sync_browser(ForceFlag(forced))
        steps.append(browser_step)
        post_version = self._resolve_installed_version(prefer_metadata=True)
        health_checks = self._postflight_health_checks()
        # Functional smoke gate (issue #294): the static checks above pass for a
        # release that still cannot launch a browser, so the operator
        # diagnostics run again here through the gate Root injected.
        health_checks = (*health_checks, *self._run_smoke_gate())
        if check.latest_version is not None:
            target_ok = (
                str(post_version) != "unknown" and compare_versions(str(post_version), check.latest_version) >= 0
            )
            if not target_ok:
                health_checks = (
                    *health_checks,
                    UpdateStepResult(
                        name="health:package_version_target",
                        executed=True,
                        success=False,
                        detail=(
                            f"installed version {post_version} is behind latest {check.latest_version}; "
                            "source synchronization did not reach the release target"
                        ),
                    ),
                )
        steps_ok = pkg_step.success and browser_step.success
        checks_ok = all(c.success for c in health_checks)
        healthy = steps_ok and checks_ok
        rolled_back = False
        rollback_status = "none"
        if not healthy and str(previous) != "unknown":
            rollback_steps = self.rollback.rollback_to(previous)
            steps.extend(rollback_steps)
            executed = [step for step in rollback_steps if step.executed]
            if not executed:
                rollback_status = "skipped"
            elif all(step.success for step in executed):
                rolled_back = True
                rollback_status = "full"
            else:
                rolled_back = any(step.success for step in executed)
                rollback_status = "partial"
                log.error("update_rollback_partial previous=%s steps=%s", previous, [s.name for s in executed])
        if not steps_ok:
            failed_detail = "; ".join(f"{s.name}: {s.detail}" for s in steps if not s.success)
            message = f"Update failed — {failed_detail}"
            if rollback_status == "partial":
                message += (
                    " Partial rollback: package restored but browser sync failed. "
                    "Run `qwen-web-arwaky update --force` to retry browser sync."
                )
        elif not checks_ok:
            failed_detail = "; ".join(f"{c.name}: {c.detail}" for c in health_checks if not c.success)
            message = f"Update steps completed but health checks failed — {failed_detail}"
        elif str(post_version) == str(previous) and not forced:
            message = (
                f"{self.package_name} already at {post_version}; environment synchronized "
                f"(Playwright Chromium verified, source {check.source})."
            )
        else:
            message = (
                f"Successfully updated {self.package_name} {previous} -> {post_version} "
                f"(latest published: {check.latest_version or 'unknown'} via {check.source})."
            )
        return UpdateReport(
            package_name=self.package_name,
            previous_version=str(previous),
            latest_version=check.latest_version,
            source=check.source,
            update_available=check.update_available,
            forced=forced,
            changed=forced or str(post_version) != str(previous),
            steps=tuple(steps),
            health_checks=tuple(health_checks),
            post_update_version=str(post_version),
            healthy=healthy,
            message=message + (f" Rolled back to {previous}." if rolled_back else ""),
            rolled_back=rolled_back,
            rollback_status=rollback_status,
        )

    # Block 3: Dunder Methods, Factories & Helpers

    def _snapshot_dir(self) -> Path:
        """Return the directory holding pre-upgrade environment snapshots."""
        return XDG_STATE_HOME / "update-snapshots"

    def _snapshot_path(self) -> Path:
        """Return the path of the most recent environment snapshot."""
        return self._snapshot_dir() / "pip-freeze.txt"

    def _capture_environment_snapshot(self, previous_version: VersionString) -> UpdateStepResult:
        """Persist a ``pip freeze`` snapshot of the current environment.

        Captured before any upgrade so rollback can restore the dependency tree
        the previous version actually ran with, not just its package code
        (issue #293).
        """
        rc, out, err = run_subprocess([sys.executable, "-m", "pip", "freeze", "--all"], timeout_sec=120.0)
        if rc != 0 or not out.strip():
            return UpdateStepResult(
                name="snapshot:environment",
                executed=True,
                success=False,
                detail=f"pip freeze failed (rc={rc}): {tail(err or out)}",
            )
        target = self._snapshot_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(out, encoding="utf-8")
        except OSError as exc:
            return UpdateStepResult(
                name="snapshot:environment",
                executed=True,
                success=False,
                detail=f"could not write snapshot to {target}: {exc}",
            )
        pinned = {
            line.split("==", 1)[0].strip().lower()
            for line in out.splitlines()
            if "==" in line and line.split("==", 1)[0].strip().lower() == self.package_name.lower()
        }
        if pinned:
            with contextlib.suppress(OSError):
                (target.parent / "pip-freeze.meta.json").write_text(
                    json.dumps({"version": str(previous_version), "package": self.package_name}),
                    encoding="utf-8",
                )
        return UpdateStepResult(
            name="snapshot:environment",
            executed=True,
            success=True,
            detail=f"pip freeze snapshot written to {target}",
        )

    def _run_smoke_gate(self) -> tuple[UpdateStepResult, ...]:
        """Run the injected functional smoke gate and normalize its results.

        The gate yields ``(name, passed, detail)`` triples (see
        ``capabilities_config_health_probe.build_smoke_gate``); failures of
        the gate itself become a failing health check so the update pipeline
        still rolls back.
        """
        try:
            gate_results = self._smoke_gate()
            return tuple(
                UpdateStepResult(
                    name=f"smoke:{name}",
                    executed=True,
                    success=bool(passed),
                    detail=detail,
                )
                for name, passed, detail in gate_results
            )
        except Exception as exc:
            return smoke_gate_unavailable(str(exc))

    def _postflight_health_checks(self) -> tuple[UpdateStepResult, ...]:
        """Verify installation integrity after the upgrade + browser sync."""
        checks: list[UpdateStepResult] = []
        py_ok = sys.version_info >= (3, 10)
        checks.append(
            UpdateStepResult(
                name="health:python_runtime",
                executed=True,
                success=py_ok,
                detail=(
                    f"Python {sys.version_info.major}.{sys.version_info.minor}."
                    f"{sys.version_info.micro} (>= 3.10 required)"
                ),
            )
        )
        version = self._resolve_installed_version(prefer_metadata=True)
        version_ok = str(version) != "unknown"
        checks.append(
            UpdateStepResult(
                name="health:package_metadata",
                executed=True,
                success=version_ok,
                detail=(
                    f"installed version resolved: {version}"
                    if version_ok
                    else "package metadata not resolvable via importlib/pip"
                ),
            )
        )
        chromium_ok = chromium_present()
        checks.append(
            UpdateStepResult(
                name="health:playwright_chromium",
                executed=True,
                success=chromium_ok,
                detail=(
                    "Chromium binary found"
                    if chromium_ok
                    else f"Chromium binary missing under {playwright_browsers_path()}"
                ),
            )
        )
        return tuple(checks)

    def _resolve_installed_version(self, *, prefer_metadata: bool = False) -> VersionString:
        """Resolve installed version from package metadata, source, or pip as a fallback."""
        if prefer_metadata:
            metadata_version = self._pip_show_version()
            if metadata_version is not None:
                return metadata_version
        v = get_package_version(self.package_name)
        if v and v != "0.0.0-dev":
            return VersionString(v)
        metadata_version = self._pip_show_version()
        return metadata_version or VersionString(v)

    def _pip_show_version(self) -> VersionString | None:
        """Read the installed distribution version using the active interpreter."""
        rc, out, _err = run_pip_show(self.package_name)
        if rc == 0:
            for line in out.splitlines():
                if line.lower().startswith("version:"):
                    return VersionString(line.split(":", 1)[1].strip())
        return None

    def __repr__(self) -> str:
        return f"UpdateVerifyCapability(package={self.package_name!r})"


__all__ = ["UpdateVerifyCapability"]
