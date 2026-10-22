"""Contract test: MCP tool schemas cannot drift from their handler signatures.

SA-3-01 shipped ``timeout_sec`` on ``process_direct_prompt``'s schema and
handler but not on the two async-capable tools, so callers could pass a
parameter the handler rejected. This suite reflects ``TOOLS`` against
``_TOOL_METHOD_MAP`` and the mapped ``McpToolCommand`` methods in both
directions: every schema property must be an accepted parameter, and every
handler parameter must be declared in the schema (``self`` and explicit
public-name aliases excepted).
"""

from __future__ import annotations

import inspect

import pytest

from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.root_mcp_main_entry import _TOOL_METHOD_MAP, TOOLS

#: Schema metadata keys; never a handler parameter.
_SCHEMA_ONLY_KEYS = frozenset({"type", "properties", "required"})

#: Handler parameters the schema deliberately does not advertise because the
#: public tool name differs: ``(tool, handler_parameter, schema_property)``.
#: ``process_direct_prompt`` accepts the schema's ``prompt`` through this
#: alias on the handler itself.
_SCHEMA_ALIASES: frozenset[tuple[str, str, str]] = {
    ("process_direct_prompt", "prompt_text", "prompt"),
}


def _handler_parameters(tool_name: str) -> dict[str, inspect.Parameter]:
    method = getattr(McpToolCommand, _TOOL_METHOD_MAP[tool_name])
    return {name: param for name, param in inspect.signature(method).parameters.items() if name != "self"}


def _schema_properties(tool_name: str) -> dict[str, object]:
    for tool in TOOLS:
        if tool.name == tool_name:
            return dict(tool.input_schema.get("properties", {}))
    raise AssertionError(f"tool {tool_name!r} is declared in _TOOL_METHOD_MAP but missing from TOOLS")


def _aliases_for(tool_name: str) -> dict[str, str]:
    return {handler_param: schema_key for tool, handler_param, schema_key in _SCHEMA_ALIASES if tool == tool_name}


@pytest.mark.parametrize("tool_name", sorted(_TOOL_METHOD_MAP))
def test_every_mapped_method_exists_on_the_tool_command(tool_name: str) -> None:
    """``_TOOL_METHOD_MAP`` must point at a real ``McpToolCommand`` method."""
    method_name = _TOOL_METHOD_MAP[tool_name]
    assert callable(getattr(McpToolCommand, method_name, None)), (
        f"{tool_name} maps to missing McpToolCommand.{method_name}"
    )


@pytest.mark.parametrize("tool_name", sorted(_TOOL_METHOD_MAP))
def test_every_schema_property_is_a_handler_parameter(tool_name: str) -> None:
    """A caller passing a declared property must not hit a TypeError."""
    handlers = _handler_parameters(tool_name)
    declared_alias_params = set(_aliases_for(tool_name).values())
    for prop in _schema_properties(tool_name):
        assert prop in handlers or prop in declared_alias_params, (
            f"schema property {tool_name}.{prop} has no handler parameter"
        )


@pytest.mark.parametrize("tool_name", sorted(_TOOL_METHOD_MAP))
def test_every_handler_parameter_is_declared_in_the_schema(tool_name: str) -> None:
    """A handler parameter the schema does not advertise is an undocumented door."""
    schema = _schema_properties(tool_name)
    aliases = _aliases_for(tool_name)
    for name, param in _handler_parameters(tool_name).items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        assert name in schema or name in aliases, (
            f"handler parameter {tool_name}.{name} is missing from the input schema"
        )


@pytest.mark.parametrize("tool_name", sorted(_TOOL_METHOD_MAP))
def test_declared_defaults_match_the_handlers_default(tool_name: str) -> None:
    """A schema default that disagrees with the handler misleads every caller."""
    schema = _schema_properties(tool_name)
    aliases = _aliases_for(tool_name)
    for name, param in _handler_parameters(tool_name).items():
        if param.default is inspect.Parameter.empty:
            continue
        declared = schema.get(aliases.get(name, name))
        if isinstance(declared, dict) and "default" in declared:
            assert declared["default"] == param.default, (
                f"{tool_name}.{name}: schema default {declared['default']!r} != handler default {param.default!r}"
            )


@pytest.mark.parametrize(
    "tool_name",
    ["process_direct_prompt", "process_prompt_file_only", "process_prompt_with_attachment"],
)
def test_prompt_tools_declare_timeout_sec(tool_name: str) -> None:
    """All three prompt tools carry the same response ceiling (SA-3-01)."""
    schema = _schema_properties(tool_name)
    handler = _handler_parameters(tool_name)

    assert "timeout_sec" in schema, f"{tool_name} must declare timeout_sec in its input schema"
    assert "timeout_sec" in handler, f"{tool_name} must accept timeout_sec as a parameter"
    assert handler["timeout_sec"].default == 120, f"{tool_name}.timeout_sec must default to 120"


def test_the_workspace_tools_public_name_is_init() -> None:
    """The registry names the tool agents call, not the handler method."""
    names = {tool.name for tool in TOOLS}
    assert "init" in names
    assert "init_workspace" not in names
    assert _TOOL_METHOD_MAP["init"] == "init_workspace"


def test_schema_metadata_keys_are_not_treated_as_parameters() -> None:
    """The drift check reads ``properties`` only; the envelope keys stay out."""
    for tool in TOOLS:
        assert set(tool.input_schema) - _SCHEMA_ONLY_KEYS == set(), f"{tool.name}: unexpected top-level schema keys"
        assert tool.input_schema.get("type") == "object"


def test_the_direct_prompt_alias_reaches_the_handler() -> None:
    """A client sending the schema's ``prompt`` key must not raise TypeError."""
    handler = _handler_parameters("process_direct_prompt")
    assert "prompt" in handler, "process_direct_prompt must accept the schema's public `prompt` name"
