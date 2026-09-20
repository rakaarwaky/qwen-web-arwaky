"""Package marker: bundled prompt templates.

The ``.md`` files in this directory are the single source of truth for
built-in role prompt templates. They are discovered at runtime by
``modules/shared/src/utility_core_prompt_template.py`` and distributed as
package data via ``modules/templates`` in the setuptools package discovery
(see ``pyproject.toml`` ``[tool.setuptools.packages.find] include``).

Adding a new file ``{role}.md`` here automatically registers a new role
template across CLI, MCP, and TUI surfaces — no code change required.
"""

__all__ = []
