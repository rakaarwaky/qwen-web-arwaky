"""Prompt template resolution: map a role name to its embedded template.

Utility layer (utility(prompt_template)): stateless helpers that read from
taxonomy constant modules. A role name may be passed anywhere a prompt file
path is accepted; this module resolves it to the bundled template without
substitution.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir

from modules.shared.src.taxonomy_analyst_constant import EMBEDDED_ANALYST_TEMPLATE
from modules.shared.src.taxonomy_architect_constant import EMBEDDED_ARCHITECT_TEMPLATE
from modules.shared.src.taxonomy_backend_constant import EMBEDDED_BACKEND_TEMPLATE
from modules.shared.src.taxonomy_core_constant import PROMPT_TEMPLATE_ROLES
from modules.shared.src.taxonomy_devops_constant import EMBEDDED_DEVOPS_TEMPLATE
from modules.shared.src.taxonomy_frontend_constant import EMBEDDED_UI_UX_TEMPLATE

_ROLE_TO_TEMPLATE: dict[str, str] = {
    "architect": EMBEDDED_ARCHITECT_TEMPLATE,
    "backend": EMBEDDED_BACKEND_TEMPLATE,
    "frontend": EMBEDDED_UI_UX_TEMPLATE,
    "analyst": EMBEDDED_ANALYST_TEMPLATE,
    "devops": EMBEDDED_DEVOPS_TEMPLATE,
}


def is_prompt_role(value: str) -> bool:
    """Return True when the value names a bundled prompt template role."""
    return value.strip().lower() in PROMPT_TEMPLATE_ROLES


def load_prompt_template(role: str) -> str:
    """Load a bundled role template as a raw markdown string.

    Args:
        role: One of ``architect``, ``backend``, ``frontend``, ``analyst``, ``devops``.

    Raises:
        ValueError: if role is not recognised.
    """
    role_key = role.strip().lower()
    if role_key not in _ROLE_TO_TEMPLATE:
        raise ValueError(
            f"Unknown prompt template role: {role!r}. "
            f"Supported: {', '.join(PROMPT_TEMPLATE_ROLES)}"
        )
    return _ROLE_TO_TEMPLATE[role_key]


def render_prompt(role: str) -> str:
    """Alias for :func:`load_prompt_template` for backward compatibility."""
    return load_prompt_template(role)


def materialize_role_template(role: str) -> Path:
    """Render a built-in role template to a stable temp file and return its path.

    The file lives in ``/tmp/qwa-templates/{role}.md`` and is overwritten on
    every call (idempotent). Used by CLI, MCP, and TUI surfaces to bridge the
    existing file-based pipelines.
    """
    rendered = load_prompt_template(role)
    tmp_dir = Path(gettempdir()) / "qwa-templates"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"{role.strip().lower()}.md"
    tmp.write_text(rendered, encoding="utf-8")
    return tmp


__all__ = [
    "is_prompt_role",
    "load_prompt_template",
    "render_prompt",
    "materialize_role_template",
]
