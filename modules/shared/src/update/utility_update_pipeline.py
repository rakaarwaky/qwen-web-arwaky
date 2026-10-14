"""Update-pipeline shared helpers (utility layer).

Stateless, domain-agnostic mechanics shared across the four update FR
capability files.  AES201 keeps capability files independent: anything two
(or more) capabilities need lives here, as plain functions, so no
capability ever imports a sibling capability.

The security-sensitive boundary is :func:`run_subprocess` — the validated
sandbox every update command flows through.  Callers pass an allowlisted
argv; the helper refuses shell metacharacters and absolute paths outside the
project root / user home / toolchain prefix, then spawns through the stdlib
``subprocess`` layer so the same code path serves every platform.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import unquote, urlparse

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_GITHUB_REPO,
    GITHUB_GIT_REF_URL,
    GITHUB_GIT_TAG_URL,
    GITHUB_REPO_ENV,
    USER_AGENT,
)
from modules.shared.src.common.taxonomy_core_vo import UpdateStepResult, VersionString

log = logging.getLogger("utility_update_pipeline")

__all__ = [
    "SUBPROCESS_FORBIDDEN_CHARS",
    "chromium_present",
    "compare_versions",
    "decode_output",
    "github_repo_name",
    "github_repo_pattern",
    "playwright_browsers_path",
    "purge_chromium_cache",
    "refuse_unverified_install",
    "resolve_editable_source_dir",
    "resolve_github_pinned_url",
    "run_pip_show",
    "run_subprocess",
    "smoke_gate_unavailable",
    "tail",
    "version_unresolvable",
]

_github_repo_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

#: Shell metacharacters refused in every subprocess argument. ``\0`` would
#: truncate the argument at the C level (argv is NUL-joined), so it is
#: refused alongside the others.
SUBPROCESS_FORBIDDEN_CHARS = set(";&|$`><\n\r\0")


# ── Version + transcript mechanics ─────────────────────────────────────


def compare_versions(left: str, right: str) -> int:
    """Return >0 when *left* is newer than *right*, <0 when older, 0 when equal."""
    left_parts = _parse_version_tuple(left)
    right_parts = _parse_version_tuple(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


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


def tail(text: str | None, max_chars: int = 400) -> str:
    """Return the trailing slice of a subprocess transcript for compact error detail."""
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"...{cleaned[-max_chars:]}"


def decode_output(data: bytes | str | None) -> str:
    """Decode captured process output without allowing invalid bytes to escape."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return bytes(data).decode("utf-8", errors="replace")


def version_unresolvable() -> VersionString:
    """Return the canonical 'unknown' version marker used when no version resolves."""
    return VersionString("unknown")


# ── GitHub repo + pinned-release mechanics ─────────────────────────────


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


# ── Editable-source + Chromium mechanics ───────────────────────────────


def read_source_version(source_dir: Path) -> str | None:
    """Read a checkout's root project version without importing its code."""
    import contextlib

    with contextlib.suppress(OSError):
        content = (source_dir / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def resolve_editable_source_dir(package_name: str) -> Path | None:
    """Detect a PEP 610 editable install or fall back to a cwd source checkout."""
    import contextlib

    dist = None
    try:
        dist = metadata.distribution(package_name)
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
        import contextlib as _cb

        with _cb.suppress(OSError):
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if re.search(rf"name\s*=\s*[\"']{re.escape(package_name)}[\"']", content):
                return cwd
    return None


def playwright_browsers_path() -> Path:
    """Resolve the Playwright browser cache honoring PLAYWRIGHT_BROWSERS_PATH."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env != "0":
        return Path(env)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


def chromium_present() -> bool:
    """True when a Playwright-cached Chromium build or a system Chromium exists."""
    browsers = playwright_browsers_path()
    if browsers.is_dir() and any(browsers.glob("chromium-*")):
        return True
    return any(shutil.which(name) for name in ("chromium", "chromium-browser", "chrome", "google-chrome"))


def purge_chromium_cache() -> int:
    """Delete cached ``chromium-*`` build directories. Returns the count purged."""
    browsers = playwright_browsers_path()
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


# ── Subprocess sandbox (the shared security boundary) ──────────────────


def approved_spawn_command(cmd: list[str]) -> list[str]:
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


def run_subprocess(cmd: list[str], *, timeout_sec: float = 60.0) -> tuple[int, str, str]:
    """Run a validated subprocess, capturing transcripts portably.

    Defensive validation: every argument must be free of shell metacharacters,
    and any absolute path argument must live under the project root, the user
    home directory, or a standard system toolchain location — preventing
    injection via manipulated package metadata or environment variables.
    """
    for arg in cmd:
        if any(ch in arg for ch in SUBPROCESS_FORBIDDEN_CHARS):
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
        spawn_cmd = approved_spawn_command(cmd)
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
            decode_output(exc.stdout or b""),
            decode_output(exc.stderr or b"") or "Subprocess execution timed out",
        )
    except FileNotFoundError as exc:
        return 127, "", f"Executable not found: {exc}"
    except OSError as exc:
        return 1, "", str(exc)
    except Exception as exc:
        return 1, "", f"Subprocess execution error: {exc}"
    return (
        completed.returncode,
        decode_output(completed.stdout or b""),
        decode_output(completed.stderr or b""),
    )


def run_pip_show(package_name: str) -> tuple[int, str, str]:
    """Run ``pip show <package>`` via the validated subprocess sandbox."""
    return run_subprocess([sys.executable, "-m", "pip", "show", package_name], timeout_sec=60.0)


# ── Refusal + smoke-gate helpers ───────────────────────────────────────


def refuse_unverified_install(target_version: str | None, mode: str) -> UpdateStepResult:
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


def smoke_gate_unavailable(reason: str) -> tuple[UpdateStepResult, ...]:
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
