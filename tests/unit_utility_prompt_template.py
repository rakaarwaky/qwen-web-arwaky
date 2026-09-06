"""Unit tests for utility_core_prompt_template."""

from __future__ import annotations

import pytest

from modules.shared.src.taxonomy_core_constant import PROMPT_TEMPLATE_ROLES
from modules.shared.src.utility_core_prompt_template import (
    is_prompt_role,
    load_prompt_template,
    materialize_role_template,
    render_prompt,
)


def test_is_prompt_role_valid() -> None:
    for role in PROMPT_TEMPLATE_ROLES:
        assert is_prompt_role(role) is True
        assert is_prompt_role(role.upper()) is True
        assert is_prompt_role(f"  {role}  ") is True


def test_is_prompt_role_invalid() -> None:
    assert is_prompt_role("not_a_role") is False
    assert is_prompt_role("") is False
    assert is_prompt_role("path/to/prompt.md") is False


def test_load_prompt_template_success() -> None:
    for role in PROMPT_TEMPLATE_ROLES:
        body = load_prompt_template(role)
        assert isinstance(body, str)
        assert len(body) > 50
        assert "# Plan:" in body


def test_load_prompt_template_unknown_role() -> None:
    with pytest.raises(ValueError, match="Unknown prompt template role"):
        load_prompt_template("invalid_role")


def test_render_prompt_alias() -> None:
    for role in PROMPT_TEMPLATE_ROLES:
        assert render_prompt(role) == load_prompt_template(role)


def test_materialize_role_template() -> None:
    for role in PROMPT_TEMPLATE_ROLES:
        path = materialize_role_template(role)
        assert path.exists()
        assert path.is_file()
        assert path.name == f"{role}.md"
        assert path.read_text(encoding="utf-8") == load_prompt_template(role)
