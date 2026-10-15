"""Update GitHub API helpers (utility layer).

GitHub repository resolution and release-pinning mechanics, split out of
``utility_update_pipeline.py``. Every request is restricted to HTTPS
``api.github.com`` and each release tag is resolved to its immutable
commit SHA before any install URL is built, so a re-pointed tag can never
silently swap the code pip installs (supply-chain fix, issue #368).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib import request
from urllib.parse import urlparse

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_GITHUB_REPO,
    GITHUB_GIT_REF_URL,
    GITHUB_GIT_TAG_URL,
    GITHUB_REPO_ENV,
    USER_AGENT,
)

log = logging.getLogger("utility_update_github")

__all__ = [
    "github_repo_pattern",
    "github_repo_name",
    "resolve_release_commit",
    "resolve_github_pinned_url",
]

_github_repo_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def github_repo_pattern() -> re.Pattern[str]:
    """Return the compiled GitHub repo-name pattern (``owner/repo``, no path)."""
    return _github_repo_pattern


def github_repo_name() -> str:
    """Resolve the configured GitHub repo, falling back to ``DEFAULT_GITHUB_REPO``."""
    repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
    if not github_repo_pattern().fullmatch(repo):
        raise ValueError(f"Invalid GitHub repository name: {repo!r}")
    return repo


def _fetch_json(url: str, timeout_sec: float = 15.0) -> dict[str, Any] | None:
    """Fetch a JSON document over HTTPS using stdlib only."""
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Only HTTPS requests to api.github.com are permitted")
        req = request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        with request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310 - HTTPS GitHub API only
            payload = json.loads(resp.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        log.debug("http_fetch_failed url=%s error=%s", url, exc)
        return None


def resolve_release_commit(target_version: str) -> tuple[str, str] | None:
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
    try:
        repo = github_repo_name()
    except ValueError:
        return None
    cleaned = target_version.strip().lstrip("vV")
    sha_pattern = re.compile(r"[0-9a-f]{40}")
    for tag in (f"v{cleaned}", cleaned):
        ref = _fetch_json(GITHUB_GIT_REF_URL.format(repo=repo, tag=tag))
        if ref is None:
            continue
        obj = ref.get("object") or {}
        sha, obj_type = str(obj.get("sha", "")), str(obj.get("type", ""))
        if not sha_pattern.fullmatch(sha):
            continue
        if obj_type == "commit":
            return tag, sha
        if obj_type == "tag":
            tag_obj = _fetch_json(GITHUB_GIT_TAG_URL.format(repo=repo, sha=sha)) or {}
            inner = tag_obj.get("object") or {}
            commit_sha = str(inner.get("sha", ""))
            if str(inner.get("type", "")) == "commit" and sha_pattern.fullmatch(commit_sha):
                return tag, commit_sha
    return None


def resolve_github_pinned_url(target_version: str | None) -> str | None:
    """Build the install URL pinned to the release's immutable commit SHA.

    Returns ``None`` when the release cannot be pinned (unknown target
    version or unresolvable tag ref); callers must then REFUSE the install
    rather than fall back to a mutable tag reference.
    """
    if not target_version:
        return None
    resolved = resolve_release_commit(target_version)
    if resolved is None:
        return None
    _tag, sha = resolved
    repo = os.getenv(GITHUB_REPO_ENV, "").strip() or DEFAULT_GITHUB_REPO
    return f"git+https://github.com/{repo}.git@{sha}"
