"""Prompt template resolution: dynamic discovery of role templates on disk.

Utility layer (utility(prompt_template)): stateless helpers that read built-in
prompt templates from the ``modules/templates/`` folder. A role name may be
passed anywhere a prompt file path is accepted; this module resolves it to the
bundled template without substitution.

Discovery is file-based: every ``.md`` file in the templates folder registers a
role (the filename without extension, lowercased). Adding a new template file
there makes it available to CLI, MCP, and TUI surfaces with no code change.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

# ``modules/shared/src`` -> ``modules`` (parents[2]) -> ``modules/templates``
_TEMPLATE_DIR: Path = Path(__file__).resolve().parents[2] / "templates"

_HEADING_RE = re.compile(r"^##\s+(?P<title>.+)$")

# Discovery cache. Keyed on the templates directory mtime rather than cached for
# the process lifetime: the MCP server is long-running, so a template dropped
# into the folder must become visible without a restart. Creating or deleting a
# file bumps the directory mtime, so a stale entry is detected with a single
# stat() instead of a full glob.
_roles_cache: tuple[str, ...] = ()
_roles_cache_key: float | None = None
_roles_cache_lock = threading.Lock()


def _templates_dir_mtime() -> float | None:
    """Directory mtime used as the discovery cache key, or None when absent."""
    try:
        return _TEMPLATE_DIR.stat().st_mtime
    except OSError:
        return None


def invalidate_template_cache() -> None:
    """Force the next discovery call to re-scan the templates folder."""
    global _roles_cache_key
    with _roles_cache_lock:
        _roles_cache_key = None


def _discovered_roles() -> tuple[str, ...]:
    """Return the sorted set of role names discoverable in the templates folder.

    A role is any file ``*.md`` directly under the templates directory.
    An empty folder yields an empty tuple. Results are cached until the
    templates directory changes.
    """
    global _roles_cache, _roles_cache_key
    key = _templates_dir_mtime()
    with _roles_cache_lock:
        if key is not None and key == _roles_cache_key:
            return _roles_cache
        if not _TEMPLATE_DIR.is_dir():
            roles: tuple[str, ...] = ()
        else:
            roles = tuple(sorted({p.stem.lower() for p in _TEMPLATE_DIR.glob("*.md") if p.is_file()}))
        _roles_cache = roles
        _roles_cache_key = key
        return roles


def list_prompt_templates() -> tuple[str, ...]:
    """Return the names of all discovered built-in prompt template roles."""
    return _discovered_roles()


def is_prompt_role(value: str) -> bool:
    """Return True when the value names a discovered prompt template role."""
    return value.strip().lower() in _discovered_roles()


def load_prompt_template(role: str) -> str:
    """Load a discovered role template as a raw markdown string.

    Args:
        role: A discovered role name, e.g. ``architect``.

    Raises:
        ValueError: if role is not a discovered template.
    """
    role_key = role.strip().lower()
    if role_key not in _discovered_roles():
        supported = ", ".join(_discovered_roles())
        raise ValueError(f"Unknown prompt template role: {role!r}. Supported: {supported}")
    return (_TEMPLATE_DIR / f"{role_key}.md").read_text(encoding="utf-8")


def render_prompt(role: str) -> str:
    """Alias for :func:`load_prompt_template` for backward compatibility."""
    return load_prompt_template(role)


def materialize_role_template(role: str) -> Path:
    """Render a built-in role template to a stable temp file and return its path.

    The file lives in ``/tmp/qwa-templates/{role}.md`` and is overwritten on
    every call (idempotent). Used by CLI, MCP, and TUI surfaces to bridge the
    existing file-based pipelines.
    """
    from tempfile import gettempdir

    rendered = load_prompt_template(role)
    tmp_dir = Path(gettempdir()) / "qwa-templates"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"{role.strip().lower()}.md"
    tmp.write_text(rendered, encoding="utf-8")
    return tmp


def _extract_title(body: str) -> str:
    """Derive a display title from the first ``##`` heading in a template body."""
    for line in body.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            return m.group("title").strip()
    return "Review"


def _extract_dimensions(body: str) -> str:
    """Derive a comma-separated list of review dimensions from ``###`` headings.

    Falls back to an empty string when the template has no ``###`` section
    headings.
    """
    dims = [line[4:].strip() for line in body.splitlines() if line.startswith("### ")]
    return ", ".join(dims)


def prompt_template_manifest() -> dict[str, dict[str, str]]:
    """Build a dynamic manifest of discovered templates.

    Returns:
        Mapping of role name to ``{"title": ..., "dimensions": ...}`` derived
        from the first ``##`` heading and the ``###`` subsections of each
        discovered template.
    """
    manifest: dict[str, dict[str, str]] = {}
    for role in _discovered_roles():
        body = load_prompt_template(role)
        manifest[role] = {"title": _extract_title(body), "dimensions": _extract_dimensions(body)}
    return manifest


__all__ = [
    "is_prompt_role",
    "list_prompt_templates",
    "load_prompt_template",
    "materialize_role_template",
    "prompt_template_manifest",
    "render_prompt",
]
