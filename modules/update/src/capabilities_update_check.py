"""Capabilities: update FR-UPDATE-001 — installed/latest version discovery.

Implements IUpdateCheckProtocol (contract_update_protocol.py).
Pure discovery: no mutation of the installed environment.
"""

from __future__ import annotations

import json
from urllib import request
from urllib.parse import urlparse

from modules.shared.src.common.taxonomy_core_constant import (
    GITHUB_RELEASE_URL,
    USER_AGENT,
)
from modules.shared.src.common.taxonomy_core_vo import UpdateCheckResult, VersionString
from modules.shared.src.common.utility_core_version import get_package_version
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.update.contract_update_protocol import IUpdateCheckProtocol
from modules.shared.src.update.utility_update_github import github_repo_name
from modules.shared.src.update.utility_update_subprocess import run_pip_show
from modules.shared.src.update.utility_update_version import compare_versions

log = get_logger("capabilities_update_check")

_github_api_host = "api.github.com"


class UpdateCheckCapability(IUpdateCheckProtocol):
    """FR-UPDATE-001: report the installed version and check for updates."""

    def __init__(
        self,
        package_name: str,
        *,
        http_timeout_sec: float = 15.0,
    ) -> None:
        self.package_name = package_name
        self.http_timeout_sec = http_timeout_sec

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

    def _resolve_installed_version(self) -> VersionString:
        """Resolve installed version from source, falling back to pip metadata."""
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

    def _discover_latest(self) -> tuple[str | None, str, str | None]:
        """Return (latest_version, source, error) via GitHub releases exclusively."""
        latest, gh_err = self._fetch_latest_github()
        if latest is not None:
            return latest, "github", None
        return None, "unavailable", f"GitHub Releases discovery failed: {gh_err}"

    def _fetch_json(self, url: str) -> dict[str, object] | None:
        """Fetch a JSON document over HTTPS using stdlib only."""
        try:
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != _github_api_host
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
        try:
            repo = github_repo_name()
        except ValueError as exc:
            return None, str(exc)
        payload = self._fetch_json(GITHUB_RELEASE_URL.format(repo=repo))
        if payload is None:
            return None, f"GitHub releases request failed for '{repo}'"
        tag = payload.get("tag_name") or payload.get("name")
        if not tag:
            return None, "GitHub release payload missing tag_name"
        return str(tag).strip().lstrip("vV"), None

    def __repr__(self) -> str:
        return f"UpdateCheckCapability(package={self.package_name!r})"


__all__ = ["UpdateCheckCapability"]
