"""Capabilities: self-update & environment synchronization (AES403).

Implements IUpdateProtocol.
Orchestrates the full self-update pipeline in chronological steps:
  Step 1: Remote version discovery via GitHub Releases API.
  Step 2: Pre-upgrade dependency snapshot (`pip freeze`) so a rollback can
          restore the environment, not just the package code.
  Step 3: Package upgrade via `git pull` (dev repos) or `pip install git+https://...`.
  Step 4: Playwright Chromium binary synchronization (`playwright install chromium`),
          with forced cache purge when --force is requested.
  Step 5: Post-flight installation-integrity health checks plus a functional
          smoke gate that re-runs the `doctor` checks as a library.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import unquote, urlparse

from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_constant import XDG_STATE_HOME
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)
from modules.shared.src.utility_core_version import get_package_version
from modules.shared.src.utility_logger_factory import get_logger

log = get_logger("capabilities_update_manager")

DEFAULT_PACKAGE_NAME = "qwen-web-arwaky"
DEFAULT_GITHUB_REPO = "rakaarwaky/qwen-web-arwaky"
GITHUB_RELEASE_URL = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_GIT_REF_URL = "https://api.github.com/repos/{repo}/git/refs/tags/{tag}"
GITHUB_GIT_TAG_URL = "https://api.github.com/repos/{repo}/git/tags/{sha}"
GITHUB_REPO_ENV = "QWEN_WEB_GITHUB_REPO"
USER_AGENT = "qwen-web-arwaky-updater/1.0"
_GITHUB_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_API_HOST = "api.github.com"


# ─── Module-level pure helpers ──────────────────────────────────────────────
def _parse_version_tuple(version: str) -> tuple[tuple[int, int, str], ...]:
    """Parse a semver-ish string into a comparable tuple (zero external deps)."""
    cleaned = str(version).strip().lstrip("vV")
    parts: list[tuple[int, int, str]] = []
    for chunk in re.split(r"[.\-+]", cleaned):
        if not chunk:
            continue
        match = re.match(r"^(\d+)(.*)$", chunk)
        if match:
            parts.append((0, int(match.group(1)), match.group(2)))
        else:
            parts.append((1, 0, chunk))
    return tuple(parts)


def compare_versions(left: str, right: str) -> int:
    """Return >0 when *left* is newer than *right*, <0 when older, 0 when equal."""
    left_parts = _parse_version_tuple(left)
    right_parts = _parse_version_tuple(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def _tail(text: str | None, max_chars: int = 400) -> str:
    """Return the trailing slice of a subprocess transcript for compact error detail."""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"...{cleaned[-max_chars:]}"


def _decode_output(data: bytes | str | None) -> str:
    """Decode captured process output without allowing invalid bytes to escape.

    ``subprocess.run(capture_output=True)`` yields bytes, but a caller-supplied
    transcript may already be text; both are accepted so the helper never
    raises on its way to reporting a subprocess failure.
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return bytes(data).decode("utf-8", errors="replace")


def _smoke_gate_unavailable(reason: str) -> tuple[UpdateStepResult, ...]:
    """Return the failing health check emitted when the smoke gate itself errored."""
    log.warning("doctor_smoke_gate_unavailable reason=%s", reason)
    return (
        UpdateStepResult(
            name="smoke:doctor_gate",
            executed=True,
            success=False,
            detail=f"functional doctor gate could not run: {reason}",
        ),
    )


# Block 1: Class Definition & Constructor
class UpdateManager(IUpdateProtocol):
    """Self-update pipeline: discovery → pip upgrade → browser sync → health checks."""

    def __init__(
        self,
        package_name: str = DEFAULT_PACKAGE_NAME,
        *,
        http_timeout_sec: float = 15.0,
        pip_timeout_sec: float = 600.0,
        browser_timeout_sec: float = 900.0,
        smoke_gate: Any = None,
    ) -> None:
        """Initialize with package identity and subprocess timeout budgets.

        ``smoke_gate`` is an optional callable that returns a tuple of
        :class:`~modules.shared.src.taxonomy_core_vo.UpdateStepResult`; the
        pipeline runs it after every successful upgrade as a functional smoke
        gate (issue #294). When omitted the pipeline falls back to a no-op gate
        that always passes.
        """
        self.package_name = package_name
        self.http_timeout_sec = http_timeout_sec
        self.pip_timeout_sec = pip_timeout_sec
        self.browser_timeout_sec = browser_timeout_sec
        self._smoke_gate = smoke_gate or (lambda: ())

    # ─── Block 2: Public Contract (IUpdateProtocol ONLY) ──
    def current_version(self) -> VersionString:
        """Return the installed package version ('unknown' when unresolvable)."""
        return self._resolve_installed_version()

    def check_update(self) -> UpdateCheckResult:
        """Compare installed vs latest published version without changing anything."""
        current = self.current_version()
        latest, source, error = self._discover_latest()
        if latest is None:
            log.warning("update_check_source_unavailable error=%s", error)
            return UpdateCheckResult(
                package_name=self.package_name,
                current_version=str(current),
                latest_version=None,
                update_available=False,
                source="unavailable",
                error=error,
            )
        update_available = str(current) == "unknown" or compare_versions(latest, str(current)) > 0
        return UpdateCheckResult(
            package_name=self.package_name,
            current_version=str(current),
            latest_version=latest,
            update_available=update_available,
            source=source,
        )

    def upgrade_package(
        self,
        force: ForceFlag = ForceFlag(False),
        *,
        target_version: str | None = None,
    ) -> UpdateStepResult:
        """Upgrade (or reinstall) the package and verify editable-source freshness."""
        editable_dir = self._editable_source_dir()
        mode_desc: str
        if editable_dir is not None:
            git_dir = editable_dir / ".git"
            git_ok = True
            source_version = self._read_source_version(editable_dir)
            if git_dir.exists():
                git_rc, git_out, git_err = self._run_subprocess(
                    ["git", "-C", str(editable_dir), "pull", "--ff-only"],
                    timeout_sec=60.0,
                )
                git_ok = git_rc == 0
                if not git_ok:
                    log.warning("editable_git_sync_failed detail=%s", _tail(git_err or git_out))
                source_version = self._read_source_version(editable_dir)
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
                repo_url = self._github_pinned_url(target_version)
                if repo_url is None:
                    return self._refuse_unverified_install(target_version, "fallback pip reinstall")
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
            repo_url = self._github_pinned_url(target_version)
            if repo_url is None:
                return self._refuse_unverified_install(target_version, "pip upgrade")
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
        rc, out, err = self._run_subprocess(cmd, self.pip_timeout_sec)
        if rc == 0:
            log.info("package_upgrade_ok mode=%s", mode_desc)
            return UpdateStepResult(name="package_upgrade", executed=True, success=True, detail=mode_desc)
        detail = _tail(err or out)
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
            purged = self._purge_chromium_cache()
            if purged:
                log.info("playwright_chromium_cache_purged dirs=%d", purged)
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
        rc, out, err = self._run_subprocess(cmd, self.browser_timeout_sec)
        if rc == 0:
            detail = "playwright install chromium"
            if purged:
                detail += f" (purged {purged} cached build(s) first)"
            log.info("browser_sync_ok")
            return UpdateStepResult(name="browser_sync", executed=True, success=True, detail=detail)
        detail = _tail(err or out)
        log.error("browser_sync_failed rc=%d detail=%s", rc, detail)
        return UpdateStepResult(
            name="browser_sync",
            executed=True,
            success=False,
            detail=f"playwright install chromium failed (rc={rc}): {detail}",
        )

    def rollback_to(self, previous_version: str) -> tuple[UpdateStepResult, ...]:
        """Reinstall the previous release and reconcile the pre-upgrade dependency snapshot.

        Restoring package code alone leaves a partial rollback when the failed
        upgrade pulled in newer transitive dependencies, so ``--no-deps`` is
        not used: pip resolves the pinned release's own dependency constraints,
        and a ``pip freeze`` snapshot taken before the upgrade is then
        reconciled so the environment matches what the previous version
        actually ran with (issue #293).
        """
        if not previous_version or previous_version == "unknown":
            return (
                UpdateStepResult(
                    "rollback",
                    False,
                    False,
                    "Cannot determine previous version for rollback. Reinstall manually with "
                    f"`pip install {self.package_name}==<previous-version>`.",
                ),
            )
        editable = self._editable_source_dir()
        if editable is not None:
            return (
                UpdateStepResult(
                    "rollback",
                    False,
                    False,
                    f"rollback to v{previous_version} is not automated for editable installations; "
                    f"revert the checkout manually: "
                    f"cd {editable} && git checkout v{previous_version} -- . && git pull --ff-only "
                    "(then reconcile dependencies from the snapshot with "
                    f"{self._snapshot_path()})",
                ),
            )
        repo_url = self._github_pinned_url(previous_version)
        if repo_url is None:
            step = self._refuse_unverified_install(previous_version, "rollback")
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
            rc, out, err = self._run_subprocess(cmd, self.pip_timeout_sec)
            package = UpdateStepResult(
                "rollback:package",
                True,
                rc == 0,
                "reinstalled " + previous_version if rc == 0 else _tail(err or out),
            )
            if rc != 0:
                return (package,)
            reconcile = self._reconcile_dependency_snapshot()
            steps = [package, *reconcile]
            browser = self.sync_browser(ForceFlag(True))
            steps.append(UpdateStepResult("rollback:browser", browser.executed, browser.success, browser.detail))
            return tuple(steps)
        except Exception as exc:
            return (UpdateStepResult("rollback", True, False, str(exc)),)

    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline."""
        forced = bool(force)
        previous = self.current_version()
        check = self.check_update()
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
        if up_to_date and not forced and self._chromium_present():
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
        pkg_step = self.upgrade_package(ForceFlag(forced), target_version=check.latest_version)
        steps.append(pkg_step)
        importlib.invalidate_caches()
        browser_step = self.sync_browser(ForceFlag(forced))
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
            rollback_steps = self.rollback_to(str(previous))
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

    # ─── Block 3: Private Helpers ──
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
        rc, out, err = self._run_subprocess(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            timeout_sec=120.0,
        )
        if rc != 0 or not out.strip():
            return UpdateStepResult(
                name="snapshot:environment",
                executed=True,
                success=False,
                detail=f"pip freeze failed (rc={rc}): {_tail(err or out)}",
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
        rc, out, err = self._run_subprocess(
            [sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "-r", str(snapshot)],
            timeout_sec=self.pip_timeout_sec,
        )
        return (
            UpdateStepResult(
                "rollback:dependencies",
                True,
                rc == 0,
                f"reconciled dependencies from {snapshot}"
                if rc == 0
                else f"dependency reconcile failed (rc={rc}): {_tail(err or out)}",
            ),
        )

    def _run_smoke_gate(self) -> tuple[UpdateStepResult, ...]:
        """Run the injected functional smoke gate and normalize its results.

        The gate yields ``(name, passed, detail)`` triples (see
        ``utility_core_doctor.build_smoke_gate``); failures of the gate itself
        become a failing health check so the update pipeline still rolls back.
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
            return _smoke_gate_unavailable(str(exc))

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
        rc, out, _err = self._run_subprocess([sys.executable, "-m", "pip", "show", self.package_name], timeout_sec=60.0)
        if rc == 0:
            for line in out.splitlines():
                if line.lower().startswith("version:"):
                    return VersionString(line.split(":", 1)[1].strip())
        return None

    def _read_source_version(self, source_dir: Path) -> str | None:
        """Read a checkout's root project version without importing its code."""
        with contextlib.suppress(OSError):
            content = (source_dir / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None

    def _github_repo_url(self, target_version: str | None = None) -> str:
        """Build a GitHub source URL, pinning to the discovered release when known."""
        repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
        if _GITHUB_REPO_PATTERN.fullmatch(repo) is None:
            raise ValueError(f"Invalid GitHub repository name: {repo!r}")
        suffix = f"@v{target_version.lstrip('vV')}" if target_version else ""
        return f"git+https://github.com/{repo}.git{suffix}"

    def _resolve_release_commit(self, target_version: str) -> tuple[str, str] | None:
        """Pin a release version to its immutable commit SHA (supply-chain fix, issue #368).

        A git tag is *mutable*: a maintainer account (or an attacker who gains
        push access) can re-point ``vX.Y.Z`` at different code, and pip cannot
        detect the swap when installing ``git+https://...@vX.Y.Z``. Resolving
        the tag to its commit SHA via the GitHub API makes the installed
        artifact immutable — a re-pointed tag can no longer silently swap the
        code pip installs. Returns ``(tag, commit_sha)`` or ``None``.
        Lightweight tags resolve in one call; annotated tags need one extra
        dereference. Both tag spellings (``vX.Y.Z`` and ``X.Y.Z``) are tried.
        """
        repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
        if _GITHUB_REPO_PATTERN.fullmatch(repo) is None:
            return None
        cleaned = target_version.strip().lstrip("vV")
        sha_pattern = re.compile(r"[0-9a-f]{40}")
        for tag in (f"v{cleaned}", cleaned):
            ref = self._fetch_json(GITHUB_GIT_REF_URL.format(repo=repo, tag=tag))
            if ref is None:
                continue
            obj = ref.get("object") or {}
            sha, obj_type = str(obj.get("sha", "")), str(obj.get("type", ""))
            if sha_pattern.fullmatch(sha) is None:
                continue
            if obj_type == "commit":
                return tag, sha
            if obj_type == "tag":
                tag_obj = self._fetch_json(GITHUB_GIT_TAG_URL.format(repo=repo, sha=sha)) or {}
                inner = tag_obj.get("object") or {}
                commit_sha = str(inner.get("sha", ""))
                if str(inner.get("type", "")) == "commit" and sha_pattern.fullmatch(commit_sha):
                    return tag, commit_sha
        return None

    def _github_pinned_url(self, target_version: str | None) -> str | None:
        """Build the install URL pinned to the release's immutable commit SHA.

        Returns ``None`` when the release cannot be pinned (unknown target
        version or unresolvable tag ref); callers must then REFUSE the
        install rather than fall back to a mutable tag reference.
        """
        if not target_version:
            return None
        resolved = self._resolve_release_commit(target_version)
        if resolved is None:
            return None
        _tag, sha = resolved
        repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
        return f"git+https://github.com/{repo}.git@{sha}"

    def _discover_latest(self) -> tuple[str | None, str, str | None]:
        """Return (latest_version, source, error) via GitHub releases exclusively."""
        latest, gh_err = self._fetch_latest_github()
        if latest is not None:
            return latest, "github", None
        return None, "unavailable", f"GitHub Releases discovery failed: {gh_err}"

    def _fetch_json(self, url: str) -> dict[str, Any] | None:
        """Fetch a JSON document over HTTPS using stdlib only."""
        try:
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != _GITHUB_API_HOST
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443)
            ):
                raise ValueError("Only HTTPS requests to api.github.com are permitted")
            req = request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with request.urlopen(req, timeout=self.http_timeout_sec) as resp:  # nosec B310 - HTTPS GitHub API only
                payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            log.debug("http_fetch_failed url=%s error=%s", url, exc)
            return None

    def _fetch_latest_github(self) -> tuple[str | None, str | None]:
        """Return (version, error) from GitHub releases."""
        repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
        if _GITHUB_REPO_PATTERN.fullmatch(repo) is None:
            return None, f"invalid GitHub repository configured (set {GITHUB_REPO_ENV}=owner/repo)"
        payload = self._fetch_json(GITHUB_RELEASE_URL.format(repo=repo))
        if payload is None:
            return None, f"GitHub releases request failed for '{repo}'"
        tag = payload.get("tag_name") or payload.get("name")
        if not tag:
            return None, "GitHub release payload missing tag_name"
        return str(tag).strip().lstrip("vV"), None

    @staticmethod
    def _refuse_unverified_install(target_version: str | None, mode: str) -> UpdateStepResult:
        """Fail-closed refusal when a release cannot be pinned to a commit SHA.

        Never falls back to a mutable tag reference (issue #368): installing
        unverifiable remote code is strictly worse than refusing the update.
        """
        detail = (
            f"{mode} refused: release {target_version!r} could not be pinned to an immutable "
            "commit SHA via the GitHub API; refusing to install unverified remote code. "
            "Check that the release tag exists and the network can reach api.github.com."
        )
        log.error("install_refused_unverified target=%s mode=%s", target_version, mode)
        return UpdateStepResult(name="package_upgrade", executed=False, success=False, detail=detail)

    def _editable_source_dir(self) -> Path | None:
        """Detect a PEP 610 editable install or fallback to cwd source checkout."""
        dist = None
        try:
            dist = metadata.distribution(self.package_name)
        except metadata.PackageNotFoundError:
            dist = None
        except Exception as exc:
            log.debug("distribution_lookup_failed error=%s", exc)
        if dist is not None:
            raw: str | None = None
            with contextlib.suppress(Exception):
                raw = dist.read_text("direct_url.json")
            if raw:
                with contextlib.suppress(ValueError, TypeError, KeyError, OSError):
                    data = json.loads(raw)
                    if isinstance(data, dict) and (data.get("dir_info") or {}).get("editable") is True:
                        parsed = urlparse(str(data.get("url", "")))
                        if parsed.scheme == "file":
                            candidate = Path(unquote(parsed.path))
                            if candidate.is_dir():
                                return candidate
        cwd = Path.cwd()
        pyproject = cwd / "pyproject.toml"
        if pyproject.is_file() and (cwd / "modules").is_dir():
            with contextlib.suppress(OSError):
                content = pyproject.read_text(encoding="utf-8", errors="ignore")
                if re.search(rf"name\s*=\s*[\"']{re.escape(self.package_name)}[\"']", content):
                    return cwd
        return None

    # \0 would truncate the argument at the C level (argv is NUL-joined), so it
    # must be refused alongside the shell metacharacters.
    _SUBPROCESS_FORBIDDEN_CHARS = set(";&|$`><\n\r\0")

    def _run_subprocess(self, cmd: list[str], timeout_sec: float) -> tuple[int, str, str]:
        """Run a subprocess capturing transcripts, portably across all platforms.

        Defensive validation: every argument must be free of shell metacharacters,
        and any absolute path argument must live under the project root, the
        user home directory, or a standard system toolchain location — preventing
        injection via manipulated package metadata or environment variables.

        The allowlist in ``_approved_spawn_command`` further pins the executable
        to a fixed shape, and the child is launched through the stdlib
        ``subprocess`` layer so the same code path serves Windows, macOS, and
        Linux. No POSIX-only primitive (``posix_spawn``, ``waitpid``,
        ``waitstatus_to_exitcode``) is used, so ``update`` runs everywhere the
        CLI itself runs.
        """
        for arg in cmd:
            if any(ch in arg for ch in self._SUBPROCESS_FORBIDDEN_CHARS):
                log.error("subprocess_rejected_argument arg=%r", arg)
                return 1, "", f"Refusing subprocess argument with shell metacharacters: {arg}"
            if arg.startswith("/"):
                p = Path(arg)
                allowed_roots = (
                    Path(__file__).resolve().parents[3],
                    Path.home(),
                    Path(sys.base_prefix),
                )
                if not any(root == p or root in p.parents for root in allowed_roots):
                    log.error("subprocess_rejected_path arg=%r", arg)
                    return 1, "", f"Refusing subprocess path outside allowed roots: {arg}"
        try:
            spawn_cmd = self._approved_spawn_command(cmd)
        except ValueError as exc:
            log.error("subprocess_rejected_command cmd=%r", cmd)
            return 1, "", str(exc)

        import subprocess  # nosec B404 - allowlisted argv, shell=False

        try:
            completed = subprocess.run(  # nosec B603 - allowlisted argv, no shell
                spawn_cmd,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return (
                124,
                _decode_output(exc.stdout or b""),
                _decode_output(exc.stderr or b"") or "Subprocess execution timed out",
            )
        except FileNotFoundError as exc:
            return 127, "", f"Executable not found: {exc}"
        except OSError as exc:
            return 1, "", str(exc)
        except Exception as exc:
            return 1, "", f"Subprocess execution error: {exc}"
        return (
            completed.returncode,
            _decode_output(completed.stdout or b""),
            _decode_output(completed.stderr or b""),
        )

    @staticmethod
    def _approved_spawn_command(cmd: list[str]) -> list[str]:
        """Map a validated update command onto a fixed, platform-neutral argv.

        ``git`` is invoked directly; ``-m pip`` / ``-m playwright`` run under the
        *current* interpreter rather than a hard-coded ``python3`` so the update
        targets the environment it was launched from on every platform.
        """
        if cmd and cmd[0] == "git":
            return [*cmd]
        if len(cmd) >= 3 and cmd[0] == sys.executable and cmd[1:2] == ["-m"] and cmd[2] in {"pip", "playwright"}:
            return [*cmd]
        raise ValueError("Unsupported update command")

    def _playwright_browsers_path(self) -> Path:
        """Resolve the Playwright browser cache honoring PLAYWRIGHT_BROWSERS_PATH and OS conventions."""
        from modules.shared.src.utility_core_paths import get_playwright_browsers_path

        return get_playwright_browsers_path()

    def _chromium_present(self) -> bool:
        """True when a Playwright-cached Chromium build or a system Chromium exists."""
        browsers = self._playwright_browsers_path()
        if browsers.is_dir() and any(browsers.glob("chromium-*")):
            return True
        return any(shutil.which(name) for name in ("chromium", "chromium-browser", "chrome", "google-chrome"))

    def _purge_chromium_cache(self) -> int:
        """Delete cached `chromium-*` build directories."""
        browsers = self._playwright_browsers_path()
        if not browsers.is_dir():
            return 0
        purged = 0
        for entry in browsers.iterdir():
            if entry.is_dir() and entry.name.startswith("chromium-"):
                try:
                    shutil.rmtree(entry)
                    purged += 1
                except OSError as exc:
                    log.warning("chromium_cache_purge_failed path=%s error=%s", entry, exc)
        return purged

    def _postflight_health_checks(self) -> tuple[UpdateStepResult, ...]:
        """Verify installation integrity."""
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
        chromium_ok = self._chromium_present()
        checks.append(
            UpdateStepResult(
                name="health:playwright_chromium",
                executed=True,
                success=chromium_ok,
                detail=(
                    "Chromium binary found"
                    if chromium_ok
                    else f"Chromium binary missing under {self._playwright_browsers_path()}"
                ),
            )
        )
        return tuple(checks)

    def __repr__(self) -> str:
        return f"UpdateManager(package={self.package_name!r})"


__all__ = ["UpdateManager", "compare_versions"]
