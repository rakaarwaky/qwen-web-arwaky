"""Capabilities: self-update & environment synchronization (AES403).

Implements IUpdateProtocol.
Orchestrates the full self-update pipeline in chronological steps:
  Step 1: Remote version discovery via GitHub Releases API.
  Step 2: Package upgrade via `git pull` (dev repos) or `pip install git+https://...`.
  Step 3: Playwright Chromium binary synchronization (`playwright install chromium`),
          with forced cache purge when --force is requested.
  Step 4: Post-flight installation-integrity health checks.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)
from modules.shared.src.utility_core_version import get_package_version

log = get_logger("capabilities_update_manager")

DEFAULT_PACKAGE_NAME = "qwen-web-cli"
DEFAULT_GITHUB_REPO = "rakaarwaky/qwen-web-arwaky"
GITHUB_RELEASE_URL = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_REPO_ENV = "QWEN_WEB_GITHUB_REPO"
USER_AGENT = "qwen-web-cli-updater/1.0"


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
    ) -> None:
        """Initialize with package identity and subprocess timeout budgets."""
        self.package_name = package_name
        self.http_timeout_sec = http_timeout_sec
        self.pip_timeout_sec = pip_timeout_sec
        self.browser_timeout_sec = browser_timeout_sec

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
                repo_url = self._github_repo_url(target_version)
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
            repo_url = self._github_repo_url(target_version)
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

    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline."""
        forced = bool(force)
        previous = self.current_version()
        check = self.check_update()
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
        pkg_step = self.upgrade_package(ForceFlag(forced), target_version=check.latest_version)
        steps.append(pkg_step)
        importlib.invalidate_caches()
        browser_step = self.sync_browser(ForceFlag(forced))
        steps.append(browser_step)
        post_version = self._resolve_installed_version(prefer_metadata=True)
        health_checks = self._postflight_health_checks()
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
        if not steps_ok:
            failed_detail = "; ".join(f"{s.name}: {s.detail}" for s in steps if not s.success)
            message = f"Update failed — {failed_detail}"
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
            message=message,
        )

    # ─── Block 3: Private Helpers ──
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
        suffix = f"@v{target_version.lstrip('vV')}" if target_version else ""
        return f"git+https://github.com/{repo}.git{suffix}"

    def _discover_latest(self) -> tuple[str | None, str, str | None]:
        """Return (latest_version, source, error) via GitHub releases exclusively."""
        latest, gh_err = self._fetch_latest_github()
        if latest is not None:
            return latest, "github", None
        return None, "unavailable", f"GitHub Releases discovery failed: {gh_err}"

    def _fetch_json(self, url: str) -> dict[str, Any] | None:
        """Fetch a JSON document over HTTPS using stdlib only."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            if not req.full_url.startswith("https://"):
                raise ValueError(f"Forbidden URL scheme: {req.full_url}")
            with urllib.request.urlopen(req, timeout=self.http_timeout_sec) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            log.debug("http_fetch_failed url=%s error=%s", url, exc)
            return None

    def _fetch_latest_github(self) -> tuple[str | None, str | None]:
        """Return (version, error) from GitHub releases."""
        repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
        if not repo:
            return None, f"no GitHub repository configured (set {GITHUB_REPO_ENV}=owner/repo)"
        payload = self._fetch_json(GITHUB_RELEASE_URL.format(repo=repo))
        if payload is None:
            return None, f"GitHub releases request failed for '{repo}'"
        tag = payload.get("tag_name") or payload.get("name")
        if not tag:
            return None, "GitHub release payload missing tag_name"
        return str(tag).strip().lstrip("vV"), None

    def _editable_source_dir(self) -> Path | None:
        """Detect a PEP 610 editable install or fallback to cwd source checkout."""
        dist = None
        try:
            dist = importlib.metadata.distribution(self.package_name)
        except importlib.metadata.PackageNotFoundError:
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

    _SUBPROCESS_FORBIDDEN_CHARS = set(";&|$`><\n\r")

    def _run_subprocess(self, cmd: list[str], timeout_sec: float) -> tuple[int, str, str]:
        """Run a subprocess capturing transcripts.

        Defensive validation: every argument must be free of shell metacharacters,
        and any absolute path argument must live under the project root, the
        user home directory, or a standard system toolchain location — preventing
        injection via manipulated package metadata or environment variables.
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
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            out = (
                exc.stdout.decode(encoding="utf-8", errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            return 124, str(out), f"Command timed out after {timeout_sec:.0f}s"
        except FileNotFoundError as exc:
            return 127, "", f"Executable not found: {exc}"
        except Exception as exc:
            return 1, "", f"Subprocess execution error: {exc}"

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
