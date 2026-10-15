"""Unit tests for utility_core_prompt_template (dynamic template discovery)."""

from __future__ import annotations

import pytest

from modules.shared.src.common.utility_core_prompt_template import (
    is_prompt_role,
    list_prompt_templates,
    load_prompt_template,
    materialize_role_template,
    prompt_template_manifest,
    render_prompt,
    resolve_prompt_role,
)

BUNDLED_ROLES = (
    "business-analyst",
    "system-analyst",
    "ui-ux-designer",
    "software-architect",
    "backend-engineer",
    "frontend-engineer",
    "product-engineer",
    "qa-engineer",
    "security-engineer",
    "devops-engineer",
)


def test_is_prompt_role_valid() -> None:
    for role in BUNDLED_ROLES:
        assert is_prompt_role(role) is True
        assert is_prompt_role(role.upper()) is True
        assert is_prompt_role(f"  {role}  ") is True


def test_is_prompt_role_invalid() -> None:
    assert is_prompt_role("not_a_role") is False
    assert is_prompt_role("") is False
    assert is_prompt_role("path/to/prompt.md") is False


def test_resolve_prompt_role_fuzzy_variants() -> None:
    """Human-typed variants of a role name resolve to the canonical key."""
    # hyphen / underscore / space are interchangeable with the canonical
    # hyphenated key, case-insensitive.
    assert resolve_prompt_role("Front-End Engineer") == "frontend-engineer"
    assert resolve_prompt_role("front-end engineer") == "frontend-engineer"
    assert resolve_prompt_role("front end engineer") == "frontend-engineer"
    assert resolve_prompt_role("frontend_engineer") == "frontend-engineer"
    assert resolve_prompt_role("frontend-engineer") == "frontend-engineer"
    assert resolve_prompt_role("QA Engineer") == "qa-engineer"
    # ui-ux-designer: the canonical key already uses hyphens; the spaced
    # form must match it too.
    assert resolve_prompt_role("UI UX Designer") == "ui-ux-designer"
    # Unknown / empty inputs stay None.
    assert resolve_prompt_role("") is None
    assert resolve_prompt_role("not_a_role") is None
    assert resolve_prompt_role("path/to/prompt.md") is None


def test_is_prompt_role_accepts_fuzzy_variants() -> None:
    """is_prompt_role delegates to fuzzy resolution, not exact-key match."""
    for variant in ("Front-End Engineer", "front end engineer", "qa_engineer"):
        assert is_prompt_role(variant) is True
    # A role name that is only a substring of a real role must not match
    # (e.g. "security" is not "security-engineer").
    assert is_prompt_role("security") is False


def test_load_and_materialize_accept_fuzzy_variants() -> None:
    """Loading / materializing a template works from any typed variant."""
    canonical = resolve_prompt_role("Front-End Engineer")
    assert canonical == "frontend-engineer"
    assert load_prompt_template("Front-End Engineer") == load_prompt_template(canonical)
    path = materialize_role_template("front end engineer")
    assert path.name == f"{canonical}.md"
    assert path.read_text(encoding="utf-8") == load_prompt_template(canonical)


def test_list_prompt_templates_returns_bundled_roles() -> None:
    discovered = list_prompt_templates()
    for role in BUNDLED_ROLES:
        assert role in discovered
    # Discovery is file-driven: every .md in modules/shared/templates shows up.
    assert len(discovered) >= len(BUNDLED_ROLES)


def test_load_prompt_template_success() -> None:
    for role in BUNDLED_ROLES:
        body = load_prompt_template(role)
        assert isinstance(body, str)
        assert len(body) > 50
        assert "# Plan:" in body


def test_load_prompt_template_unknown_role() -> None:
    with pytest.raises(ValueError, match="Unknown prompt template role"):
        load_prompt_template("invalid_role")


def test_render_prompt_alias() -> None:
    for role in BUNDLED_ROLES:
        assert render_prompt(role) == load_prompt_template(role)


def test_materialize_role_template() -> None:
    for role in BUNDLED_ROLES:
        path = materialize_role_template(role)
        assert path.exists()
        assert path.is_file()
        assert path.name == f"{role}.md"
        assert path.read_text(encoding="utf-8") == load_prompt_template(role)


def test_prompt_template_manifest_dynamic() -> None:
    manifest = prompt_template_manifest()
    assert set(manifest.keys()) == set(list_prompt_templates())
    for role in BUNDLED_ROLES:
        entry = manifest[role]
        assert "title" in entry
        assert "dimensions" in entry
        assert len(entry["title"]) > 0


def test_discovery_picks_up_new_template_file(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new .md dropped in the templates folder is discovered automatically."""
    import modules.shared.src.common.utility_core_prompt_template as mod

    # Point the module's template dir at a fresh folder with one new role.
    scratch = tmp_path_factory.mktemp("templates")
    (scratch / "security.md").write_text("# Plan: {feature} — Security\n\n## Summary\n\nBody\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", scratch)
    mod.invalidate_template_cache()
    try:
        assert "security" in list_prompt_templates()
        assert is_prompt_role("security")
        assert "security" in prompt_template_manifest()
        assert load_prompt_template("security").startswith("# Plan:")
    finally:
        mod.invalidate_template_cache()
