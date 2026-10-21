#!/usr/bin/env python3
"""Validate the shared kernel barrel ``__all__`` (ARCH-4-001).

The shared barrel ``modules/shared/src/__init__.py`` re-exports the taxonomy,
contract, and utility symbols the other members consume. Two classes of drift
broke it before this gate existed:

1. **Phantom exports** — a name listed in ``__all__`` that the module never
   imports, so ``from modules.shared.src import Phantom`` raises
   ``ImportError`` at runtime while static readers believe the symbol exists.
2. **Bare package names** — sub-package names (``modules``, ``browser``,
   ``common``, …) listed as if they were symbols, which shadows real exports
   and tells readers a folder is a re-exported value.

The CI gate exits non-zero on either. Run it directly or via ``scripts/ci.sh``.

Exit codes:
    0 — ``__all__`` is sound
    1 — phantom export, bare package name, or duplicate found
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BARREL = PROJECT_ROOT / "modules" / "shared" / "src" / "__init__.py"

# Sub-package names re-exported as attributes by the barrel (AES702). They are
# legitimate module attributes but must not masquerade as value symbols in
# ``__all__``.
SUBPACKAGE_NAMES = frozenset(
    {
        "modules",
        "browser",
        "common",
        "config",
        "jobs",
        "logging",
        "prompt",
        "session",
        "swarm",
        "update",
    }
)


def _collect_all(tree: ast.Module) -> list[str]:
    """Return every string listed in ``__all__`` (concatenation included)."""
    names: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == "__all__"):
                continue
            for element in _flatten(node.value):
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.append(element.value)
    return names


def _flatten(node: ast.expr) -> list[ast.expr]:
    """Flatten ``_all += [...]`` / list concatenation into literal elements."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return list(node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten(node.left) + _flatten(node.right)
    return [node]


def _collected_imports(tree: ast.Module) -> set[str]:
    """Return every name the module binds via ``import`` or ``from ... import``."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
    return bound


def main() -> int:
    if not BARREL.exists():
        print(f"[shared-barrel] missing barrel: {BARREL}", file=sys.stderr)
        return 1

    source = BARREL.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BARREL))

    listed = _collect_all(tree)
    bound = _collected_imports(tree)

    failures: list[str] = []

    phantoms = sorted({name for name in listed if name not in bound})
    if phantoms:
        failures.append(
            "phantom exports in __all__ (no matching import or assignment): " + ", ".join(phantoms)
        )

    bare = sorted({name for name in listed if name in SUBPACKAGE_NAMES})
    if bare:
        failures.append(
            "bare sub-package names in __all__ (ARCH-4-001): " + ", ".join(bare)
        )

    dupes = sorted({name for name in listed if listed.count(name) > 1})
    if dupes:
        failures.append("duplicate entries in __all__: " + ", ".join(dupes))

    for failure in failures:
        print(f"[shared-barrel] FAIL {failure}", file=sys.stderr)

    if failures:
        print(
            f"[shared-barrel] FAIL {BARREL.relative_to(PROJECT_ROOT)}: "
            f"{len(failures)} problem(s)",
            file=sys.stderr,
        )
        return 1

    print(f"[shared-barrel] OK {BARREL.relative_to(PROJECT_ROOT)}: {len(listed)} exports, no phantoms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
