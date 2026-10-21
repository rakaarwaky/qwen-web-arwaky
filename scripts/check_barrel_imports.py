#!/usr/bin/env python3
"""Forbid barrel imports of the shared kernel outside its own ``__init__`` (ARCH-4-003).

``from modules.shared.src import X`` resolves through the barrel, which pulls
every taxonomy, contract, and utility module in the shared member into the
importing module's dependency graph. Direct submodule imports
(``from modules.shared.src.common.taxonomy_core_vo import AppConfig``) carry
only what the file needs, so a change in one domain does not cascade through
every consumer of the barrel.

The barrel itself must keep its own re-export statements, so
``modules/shared/src/__init__.py`` is the single allowed site. Every other
``.py`` file under the repository is checked.

The checker is AST-based (no import execution), so it runs fast enough to sit
in CI and never needs the package importable.

Exit codes:
    0 — no barrel imports outside the barrel
    1 — one or more files import the shared barrel
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BARREL_MODULE = "modules.shared.src"
# The barrel re-exports everything; it is the one file allowed to import itself.
ALLOWED_FILES = frozenset(
    {
        (PROJECT_ROOT / "modules" / "shared" / "src" / "__init__.py").resolve(),
    }
)

# Sub-module paths that are NOT the barrel: imports of these are already direct
# and therefore fine. Only the bare package form is a violation.


def _is_barrel_import(node: ast.ImportFrom) -> bool:
    """Return True when the statement imports the shared barrel itself."""
    if node.level:  # relative import — never the absolute barrel path
        return False
    parts = []
    if node.module:
        parts = node.module.split(".")
    return parts == ["modules", "shared", "src"]


def find_barrel_imports(path: Path) -> list[tuple[int, str]]:
    """Return ``(line_number, statement)`` pairs for barrel imports in *path*."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _is_barrel_import(node):
            aliases = ", ".join(alias.asname or alias.name for alias in node.names)
            hits.append((node.lineno, f"from {node.module} import {aliases}"))
    return hits


def main() -> int:
    failures: list[str] = []

    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if ".venv" in path.parts or "node_modules" in path.parts or "dist" in path.parts:
            continue
        if "__pycache__" in path.parts:
            continue
        if path.resolve() in ALLOWED_FILES:
            continue

        for lineno, statement in find_barrel_imports(path):
            failures.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {statement}")

    if failures:
        print("[barrel-imports] FAIL barrel imports outside modules/shared/src/__init__.py:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(
            "[barrel-imports] FIX import the symbol from its direct submodule, e.g. "
            "from modules.shared.src.common.taxonomy_core_vo import AppConfig",
            file=sys.stderr,
        )
        return 1

    print("[barrel-imports] OK no barrel imports of modules.shared.src outside the barrel itself")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
