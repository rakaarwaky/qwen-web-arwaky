"""Capabilities: update FR-UPDATE-002 — package upgrade and browser sync.

Implements IUpdateUpgradeProtocol (contract_update_protocol.py).
Owns the package-upgrade and browser-sync business rules; the shared
subprocess sandbox, pinned-release resolution, editable-source detection,
and Chromium cache mechanics live in the focused update utility modules so this
capability stays independent of its sibling capability files (AES201).
"""

from __future__ import annotations

import sys

from modules.shared.src.common.taxonomy_core_constant import DEFAULT_PACKAGE_NAME
from modules.shared.src.common.taxonomy_core_vo import ForceFlag, UpdateStepResult
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.update.contract_update_protocol import IUpdateUpgradeProtocol
from modules.shared.src.update.utility_update_chromium import chromium_present, purge_chromium_cache
from modules.shared.src.update.utility_update_github import resolve_github_pinned_url
from modules.shared.src.update.utility_update_refusal import refuse_unverified_install
from modules.shared.src.update.utility_update_source import read_source_version, resolve_editable_source_dir
from modules.shared.src.update.utility_update_subprocess import run_subprocess, tail
from modules.shared.src.update.utility_update_version import compare_versions

log = get_logger("capabilities_update_upgrade")


# Block 1: Class Definition & Constructor


class UpdateUpgradeCapability(IUpdateUpgradeProtocol):
    """FR-UPDATE-002: upgrade the package and synchronise the browser build."""

    def __init__(
        self,
        package_name: str = DEFAULT_PACKAGE_NAME,
        *,
        pip_timeout_sec: float = 600.0,
        browser_timeout_sec: float = 900.0,
    ) -> None:
        self.package_name = package_name
        self.pip_timeout_sec = pip_timeout_sec
        self.browser_timeout_sec = browser_timeout_sec

    # Block 2: Protocol Method Implementation

    def upgrade_package(
        self,
        force: ForceFlag = ForceFlag(False),
        *,
        target_version: str | None = None,
    ) -> UpdateStepResult:
        """Upgrade (or reinstall) the package and verify editable-source freshness."""
        editable_dir = resolve_editable_source_dir(self.package_name)
        mode_desc: str
        if editable_dir is not None:
            git_dir = editable_dir / ".git"
            git_ok = True
            source_version = read_source_version(editable_dir)
            if git_dir.exists():
                git_rc, git_out, git_err = run_subprocess(
                    ["git", "-C", str(editable_dir), "pull", "--ff-only"],
                    timeout_sec=60.0,
                )
                git_ok = git_rc == 0
                if not git_ok:
                    log.warning("editable_git_sync_failed detail=%s", tail(git_err or git_out))
                source_version = read_source_version(editable_dir)
            source_is_stale = target_version is not None and (
                source_version is None or compare_versions(source_version, target_version) < 0
            )
            if git_ok and not source_is_stale:
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--disable-pip-version-check",
                    "-e",
                    str(editable_dir),
                ]
                mode_desc = f"git pull & editable reinstall from {editable_dir}"
            else:
                repo_url = resolve_github_pinned_url(target_version)
                if repo_url is None:
                    return refuse_unverified_install(target_version, "fallback pip reinstall")
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--disable-pip-version-check",
                    "--upgrade",
                    "--force-reinstall",
                    "--no-deps",
                    repo_url,
                ]
                mode_desc = f"fallback pip reinstall from GitHub ({repo_url})"
        else:
            repo_url = resolve_github_pinned_url(target_version)
            if repo_url is None:
                return refuse_unverified_install(target_version, "pip upgrade")
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-input",
                "--disable-pip-version-check",
                "--upgrade",
                repo_url,
            ]
            if bool(force):
                cmd.extend(["--force-reinstall", "--no-deps"])
            mode_desc = f"pip upgrade from GitHub ({repo_url})"
        log.info("package_upgrade_started mode=%s", mode_desc)
        rc, out, err = run_subprocess(cmd, timeout_sec=self.pip_timeout_sec)
        if rc == 0:
            log.info("package_upgrade_ok mode=%s", mode_desc)
            return UpdateStepResult(name="package_upgrade", executed=True, success=True, detail=mode_desc)
        detail = tail(err or out)
        log.error("package_upgrade_failed rc=%d detail=%s", rc, detail)
        return UpdateStepResult(
            name="package_upgrade",
            executed=True,
            success=False,
            detail=f"{mode_desc} failed (rc={rc}): {detail}",
        )

    def sync_browser(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Synchronize Playwright Chromium binaries."""
        purged = 0
        if bool(force):
            purged = purge_chromium_cache()
            if purged:
                log.info("playwright_chromium_cache_purged dirs=%d", purged)
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        rc, out, err = run_subprocess(cmd, timeout_sec=self.browser_timeout_sec)
        if rc == 0:
            detail = "playwright install chromium"
            if purged:
                detail += f" (purged {purged} cached build(s) first)"
            log.info("browser_sync_ok")
            return UpdateStepResult(name="browser_sync", executed=True, success=True, detail=detail)
        detail = tail(err or out)
        log.error("browser_sync_failed rc=%d detail=%s", rc, detail)
        return UpdateStepResult(
            name="browser_sync",
            executed=True,
            success=False,
            detail=f"playwright install chromium failed (rc={rc}): {detail}",
        )

    def chromium_is_present(self) -> bool:
        """Expose the shared Chromium-presence check (used by the verify gate)."""
        return chromium_present()

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        return f"UpdateUpgradeCapability(package={self.package_name!r})"


__all__ = ["UpdateUpgradeCapability"]
