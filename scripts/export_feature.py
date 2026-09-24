#!/usr/bin/env python3
"""Export a selected module into a single consolidated Markdown file.

The output includes the module's own source files, pyproject.toml (or setup.cfg),
important feature documentation (PRD.md, FRD.md, ARCHITECTURE.md), and any shared module
transitively reachable through ``from modules.shared`` or ``import modules.shared``
import paths.

Import analysis uses AST parsing with regex fallback for robust handling of:
- multiline imports
- aliased imports
- relative imports within shared module
- wildcard imports with symbol-level filtering

Usage:
    # Interactive mode (prompts for selection):
    python3 scripts/export/export_feature.py

    # CLI mode (non-interactive):
    python3 scripts/export/export_feature.py --module server
    python3 scripts/export/export_feature.py --module telemetry --output /tmp/out.md
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Sanitize version strings to a safe filename fragment (CWE-22 mitigation).
SAFE_VERSION_CHARS = re.compile(r"[^0-9A-Za-z.\-]")

IMPORTANT_FILES = {
    "pyproject.toml",
    "setup.cfg",
    "README.md",
    "PRD.md",
    "FRD.md",
    "ARCHITECTURE.md",
    "RULES_AES.md",
}

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
}


def _is_excluded(path: Path) -> bool:
    """Return True if the path is inside an excluded directory."""
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def list_modules(modules_dir: Path) -> list[str]:
    """Sorted list of module directory names that contain Python source files."""
    modules: list[str] = []
    for entry in modules_dir.iterdir():
        if not entry.is_dir() or _is_excluded(entry):
            continue
        # Check if module has .py files (in src/ subdir or directly)
        src_dir = entry / "src"
        base_dir = src_dir if src_dir.exists() else entry
        try:
            has_py = any(f.is_file() and not _is_excluded(f) for f in base_dir.rglob("*.py"))
        except OSError:
            continue
        if has_py:
            modules.append(entry.name)
    return sorted(modules)


def prompt_module(modules: list[str]) -> str:
    """Show numbered list, prompt for selection, return the chosen module name."""
    print("Available modules:")
    for i, name in enumerate(modules, 1):
        print(f"{i:2d}) {name}")
    print()

    while True:
        try:
            choice = input(f"Select a module (1-{len(modules)}) or 'q' to quit: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)

        if choice.lower() == "q":
            print("Exiting.")
            sys.exit(0)

        try:
            idx = int(choice) - 1
        except ValueError:
            print("Error: Invalid input. Please enter a valid number or 'q'.")
            continue

        if 0 <= idx < len(modules):
            return modules[idx]
        print(f"Error: Please choose a number between 1 and {len(modules)}.")


def resolve_workspace() -> tuple[Path, Path]:
    """Return (workspace_root, modules_dir). Exit on missing modules/."""
    workspace_root = Path(__file__).resolve().parent.parent
    modules_dir = workspace_root / "modules"

    if not modules_dir.exists():
        print(f"Error: 'modules' directory not found at {modules_dir}", file=sys.stderr)
        sys.exit(1)
    return workspace_root, modules_dir


def read_version(workspace_root: Path, fallback: str = "0.1.0") -> str:
    """Read version from pyproject.toml or setup.cfg."""
    pyproject = workspace_root / "pyproject.toml"

    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Warning: Could not read {pyproject} ({e}). Defaulting to {fallback}.")
            return fallback

        # Prefer proper TOML parsing when available.
        try:
            import tomllib  # Python 3.11+

            data = tomllib.loads(text)
            version = data.get("project", {}).get("version") or data.get("tool", {}).get("poetry", {}).get("version")
            if version:
                return str(version)
        except ModuleNotFoundError:
            pass
        except Exception as e:
            print(f"Warning: Failed to parse {pyproject} as TOML ({e}); falling back to regex.")

        # Regex fallback: version = "1.2.3" or version = '1.2.3'
        match = re.search(
            r"""^version\s*=\s*['"]([^'"]+)['"]""",
            text,
            re.MULTILINE,
        )
        if match:
            return match.group(1)

    setup_cfg = workspace_root / "setup.cfg"
    if setup_cfg.exists():
        try:
            text = setup_cfg.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"""^version\s*=\s*(.+?)\s$""", text, re.MULTILINE)
            if match:
                return match.group(1)
        except OSError as e:
            print(f"Warning: Could not read {setup_cfg} ({e}). Defaulting to {fallback}.")

    return fallback


def sanitize_version(version: str) -> str:
    """CWE-22: strip any character that could escape the .agents/finding directory."""
    safe = SAFE_VERSION_CHARS.sub("_", version)
    return safe or "0.0.0"


def index_shared_symbols(shared_src_dir: Path) -> dict[str, list[Path]]:
    """Index class/function symbols inside modules/shared/src.

    This helps resolve cases like:
        from modules.shared.src.common import SomeClass
    """
    symbol_to_files: dict[str, list[Path]] = {}

    if not shared_src_dir.exists():
        print("Warning: 'modules/shared/src' directory not found. Shared dependencies cannot be resolved.")
        return symbol_to_files

    print("Indexing shared module symbols...")

    for f in shared_src_dir.rglob("*.py"):
        if _is_excluded(f):
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Warning: Failed to index file {f} ({e})")
            continue

        try:
            tree = ast.parse(content, filename=str(f))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol_to_files.setdefault(node.name, []).append(f)
        except (SyntaxError, ValueError):
            # Fallback: regex for files that cannot be parsed as valid Python.
            decl_pattern = re.compile(r"\b(?:class|def|async\s+def)\s+([A-Za-z_]\w*)")
            for match in decl_pattern.finditer(content):
                symbol_to_files.setdefault(match.group(1), []).append(f)

    return symbol_to_files


def _unique_variants(name: str) -> list[str]:
    """Return unique underscore/dash variants of a name."""
    variants = [name]
    if "_" in name:
        variants.append(name.replace("_", "-"))
    if "-" in name:
        variants.append(name.replace("-", "_"))
    return list(dict.fromkeys(variants))


def _find_dir(directory: Path, name: str) -> Path | None:
    """Find a directory by name, allowing underscore/dash variants."""
    for candidate_name in _unique_variants(name):
        candidate = directory / candidate_name
        if candidate.is_dir() and not _is_excluded(candidate):
            return candidate
    return None


def _find_file(directory: Path, name: str) -> Path | None:
    """Find a Python file by module name, allowing underscore/dash variants."""
    for candidate_name in _unique_variants(name):
        candidate = directory / f"{candidate_name}.py"
        if candidate.is_file() and not _is_excluded(candidate):
            return candidate
    return None


def _resolve_module_path(
    start_dir: Path,
    parts: list[str],
    symbol_to_files: dict[str, list[Path]],
) -> tuple[set[Path], Path | None]:
    """Resolve dotted parts to files under start_dir.

    Returns:
        (resolved_files, package_dir)

        package_dir is not None when the resolved path points to a package
        directory, allowing imported names to be resolved as submodules.
    """
    resolved: set[Path] = set()
    current_dir = start_dir

    if not parts:
        init_py = current_dir / "__init__.py"
        if init_py.is_file() and not _is_excluded(init_py):
            resolved.add(init_py)
        return resolved, current_dir

    for i, part in enumerate(parts):
        found_dir = _find_dir(current_dir, part)

        if found_dir is not None:
            init_py = found_dir / "__init__.py"
            if init_py.is_file() and not _is_excluded(init_py):
                resolved.add(init_py)
            current_dir = found_dir
            continue

        found_file = _find_file(current_dir, part)

        if found_file is not None:
            resolved.add(found_file)
            # Remaining parts are likely symbols/attributes.
            for symbol in parts[i + 1 :]:
                resolved.update(symbol_to_files.get(symbol, []))
            return resolved, None

        # If path segment is not found as module/package, assume symbol.
        resolved.update(symbol_to_files.get(part, []))
        for symbol in parts[i + 1 :]:
            resolved.update(symbol_to_files.get(symbol, []))
        return resolved, None

    return resolved, current_dir


def _code_fence(content: str) -> str:
    """Return a Markdown fence long enough not to collide with content."""
    runs = re.findall(r"`+", content)
    longest = max((len(run) for run in runs), default=0)
    return "`" * max(3, longest + 1)


def _language_for(path: Path) -> str:
    """Pick a fenced-code-block language identifier based on file extension."""
    if path.name == "pyproject.toml":
        return "toml"
    if path.name == "setup.cfg":
        return "ini"
    if path.suffix == ".py":
        return "python"
    if path.suffix in (".js", ".ts"):
        return "javascript"
    if path.suffix == ".md":
        return "markdown"
    return ""


def _parse_import_names(raw: str) -> list[str]:
    """Parse imported symbol names from a from-import clause."""
    names: list[str] = []
    # Remove anything after semicolon.
    raw = raw.split(";", 1)[0]
    for part in raw.split(","):
        # Remove comments.
        part = part.split("#", 1)[0].strip()
        if not part:
            continue
        # Remove alias: "foo as bar" -> "foo"
        name = part.split(" as ", 1)[0].strip()
        if name and name != "*":
            names.append(name)
    return names


def _detect_wildcard_shared_imports(
    content: str,
) -> list[tuple[str, set[str]]]:
    """Detect parenthesized wildcard imports from modules.shared.src.

    Returns list of (module_path, set_of_symbol_names).
    Uses regex because AST parsing flattens parenthesized imports into
    individual names, losing the "wildcard" grouping information needed
    for __init__.py symbol filtering.
    """
    results: list[tuple[str, set[str]]] = []
    pattern = re.compile(
        r"\bfrom\s+(modules\.shared\.(?:src(?:\.[a-zA-Z0-9_]+)*)?)\s+import\s+\(([^)]+)\)",
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        module = m.group(1)
        symbols_str = m.group(2)
        symbols: set[str] = set()
        for line in symbols_str.split("\n"):
            for sym in line.strip().split(","):
                sym = sym.strip()
                if sym and not sym.startswith("("):
                    symbols.add(sym)
        results.append((module, symbols))
    return results


def _extract_imports(
    content: str,
    filename: Path,
) -> list[tuple[str | None, list[str], int]]:
    """Extract imports from Python source using AST with regex fallback.

    Returns tuples:
        (module, imported_names, level)

    Examples:
        ("modules.shared.src.common", ["helper"], 0)
        ("common.helper", ["HelperClass"], 1)
    """
    try:
        tree = ast.parse(content, filename=str(filename))
    except (SyntaxError, ValueError):
        return _extract_imports_regex(content)

    imports: list[tuple[str | None, list[str], int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, [], 0))
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names if alias.name != "*"]
            imports.append((node.module, names, node.level))

    return imports


def _extract_imports_regex(content: str) -> list[tuple[str | None, list[str], int]]:
    """Regex fallback for extracting shared imports."""
    imports: list[tuple[str | None, list[str], int]] = []
    # Pattern for from modules.shared.src... import ...
    abs_shared_from_regex = re.compile(
        r"\bfrom\s+(modules\.shared\.src(?:\.[A-Za-z0-9_]+)*)\s+import\s+"
        r"(?:\(([^)]*)\)|([^\n]+))",
        re.DOTALL,
    )
    # Pattern for import modules.shared.src...
    abs_shared_path_regex = re.compile(r"\bmodules\.shared\.src(?:\.[A-Za-z0-9_]+)*\b")

    for match in abs_shared_from_regex.finditer(content):
        module = match.group(1)
        raw_names = match.group(2) or match.group(3) or ""
        names = _parse_import_names(raw_names)
        imports.append((module, names, 0))

    for match in abs_shared_path_regex.finditer(content):
        imports.append((match.group(0), [], 0))
    return imports


def _absolute_shared_parts(module: str) -> list[str] | None:
    """Convert absolute modules.shared.src... import to parts under shared/src.

    Examples:
        modules.shared.src -> []
        modules.shared.src.common -> ["common"]
        modules.shared.src.common.helper -> ["common", "helper"]
    """
    if module == "modules.shared.src":
        return []
    if module.startswith("modules.shared.src."):
        return module[len("modules.shared.src.") :].split(".")
    if module.startswith("modules.shared."):
        remainder = module[len("modules.shared.") :]
        if remainder == "src":
            return []
        if remainder.startswith("src."):
            return remainder[len("src.") :].split(".")
        return remainder.split(".")
    return None


def _package_parts_for_shared_file(
    file: Path,
    shared_src_dir: Path,
) -> list[str]:
    """Return package parts for a Python file under modules/shared/src."""
    try:
        rel = file.relative_to(shared_src_dir)
    except ValueError:
        return []
    parts = list(rel.parts)
    if not parts:
        return []
    # Drop the filename. Works for both module.py and package/__init__.py.
    return parts[:-1]


def _files_for_shared_parts(
    parts: list[str],
    imported_names: list[str],
    shared_src_dir: Path,
    symbol_to_files: dict[str, list[Path]],
) -> set[Path]:
    """Resolve shared import path parts and imported names to files."""
    files, package_dir = _resolve_module_path(
        shared_src_dir,
        parts,
        symbol_to_files,
    )

    if package_dir is not None:
        for name in imported_names:
            if not name or name == "*":
                continue
            sub_files, _ = _resolve_module_path(package_dir, [name], symbol_to_files)
            files.update(sub_files)
            files.update(symbol_to_files.get(name, []))

    else:
        for name in imported_names:
            if not name or name == "*":
                continue
            files.update(symbol_to_files.get(name, []))

    return {f for f in files if not _is_excluded(f)}


def _files_for_import(
    module: str | None,
    imported_names: list[str],
    level: int,
    source_file: Path,
    shared_src_dir: Path,
    symbol_to_files: dict[str, list[Path]],
) -> set[Path]:
    """Resolve one import statement to shared files."""
    # Relative import (e.g., from .common import helper)
    if level > 0:
        if not shared_src_dir.exists():
            return set()
        try:
            source_file.relative_to(shared_src_dir)
        except ValueError:
            return set()

        package_parts = _package_parts_for_shared_file(source_file, shared_src_dir)

        if level == 1:
            base_parts = package_parts
        else:
            drop = level - 1
            if drop > len(package_parts):
                return set()
            base_parts = package_parts[: len(package_parts) - drop] if drop else package_parts

        module_parts = module.split(".") if module else []
        return _files_for_shared_parts(base_parts + module_parts, imported_names, shared_src_dir, symbol_to_files)

    # Absolute import.
    if not module:
        return set()

    parts = _absolute_shared_parts(module)
    if parts is None:
        return set()

    return _files_for_shared_parts(parts, imported_names, shared_src_dir, symbol_to_files)


def expand_shared_dependencies(
    initial_files: set[Path],
    shared_src_dir: Path,
    symbol_to_files: dict[str, list[Path]],
) -> set[Path]:
    """Transitively expand shared dependencies from initial files.

    Uses AST-based import extraction with regex-based wildcard detection
    for symbol-level filtering (e.g., from modules.shared.src import (A, B)).
    This prevents pulling in unused __init__.py re-exports.
    """
    print("Scanning source files for shared dependencies...")

    if not shared_src_dir.exists():
        return set(initial_files)

    all_files = set(initial_files)
    scanned: set[Path] = set()
    # Track __init__.py files resolved during transitive expansion
    # so they won't be scanned (their imports would pull in full subpackages)
    init_py_resolved: set[Path] = set()

    while True:
        pending = [f for f in all_files if f.suffix == ".py" and f not in scanned and not _is_excluded(f)]

        if not pending:
            break

        discovered: set[Path] = set()

        for f in pending:
            scanned.add(f)
            # Skip scanning __init__.py files resolved during transitive expansion
            if f.name == "__init__.py" and f in init_py_resolved:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"Warning: Failed to read {f} for import analysis ({e})")
                continue

            # Detect wildcard imports (regex-based, AST flattens them)
            wildcard_imports = _detect_wildcard_shared_imports(content)

            imports = _extract_imports(content, f)

            for module, names, level in imports:
                # Skip bare "from . import (subpkg1, subpkg2)" patterns
                # These pull in entire subpackages and should be handled
                # by symbol-level filtering, not full transitive expansion.
                # Detection: module is None, level > 0, all names are lowercase (package dirs)
                if module is None and level > 0 and len(names) > 1:
                    is_package_barrel = all(n == n.lower() and "." not in n for n in names)
                    if is_package_barrel:
                        continue

                try:
                    resolved = _files_for_import(module, names, level, f, shared_src_dir, symbol_to_files)

                    # Check if this import corresponds to a wildcard pattern
                    wc_symbols = None
                    for wc_module, wc_set in wildcard_imports:
                        parts = _absolute_shared_parts(wc_module)
                        if parts is None:
                            continue
                        # Convert module path to parts and compare
                        if module == wc_module:
                            wc_symbols = wc_set
                            break

                    # Apply __init__.py symbol filtering for wildcard imports
                    if wc_symbols:
                        filtered = set()
                        for rf in resolved:
                            if rf.name == "__init__.py":
                                filtered.update(
                                    _resolve_init_py_imports(rf, shared_src_dir, required_symbols=wc_symbols)
                                )
                            else:
                                filtered.add(rf)
                        discovered.update(filtered)
                    else:
                        discovered.update(resolved)

                    # Track __init__.py files resolved during transitive expansion
                    # so they won't be scanned (their imports would pull in full subpackages)
                    for rf in resolved:
                        if rf.name == "__init__.py":
                            init_py_resolved.add(rf)

                except Exception as e:
                    print(f"Warning: Failed resolving import in {f}: {e}")

        before = len(all_files)
        all_files.update(discovered)

        if len(all_files) == before:
            break

    return all_files


def collect_module_files(module_path: Path, workspace_root: Path) -> set[Path]:
    """Collect Python files, important docs/config, and all skill markdown for a module.

    Args:
        module_path: Path to the module directory.
        workspace_root: Path to the workspace root.

    Returns:
        Set of paths to include in the export.
    """
    files: set[Path] = set()

    # Workspace-root important files.
    if workspace_root.exists():
        try:
            for f in workspace_root.iterdir():
                if f.is_file() and f.name in IMPORTANT_FILES:
                    files.add(f)
        except OSError as e:
            print(f"Warning: Failed scanning workspace root files ({e})")

    # Module-level important files.
    if module_path.exists():
        try:
            for f in module_path.iterdir():
                if f.is_file() and f.name in IMPORTANT_FILES:
                    files.add(f)
        except OSError as e:
            print(f"Warning: Failed scanning module-level files ({e})")

    # Module Python sources.
    src_dir = module_path / "src"
    base_dir = src_dir if src_dir.exists() else module_path

    for f in base_dir.rglob("*.py"):
        if f.is_file() and not _is_excluded(f):
            files.add(f)

    return files


def _extract_init_py_symbols(init_py_path: Path) -> dict[str, list[Path]]:
    """Extract which file each symbol in __init__.py comes from.

    Returns a dict mapping symbol name (e.g., "ActionName") to the file(s) that define it.
    Handles multiline imports properly.
    """
    symbol_map: dict[str, list[Path]] = {}

    try:
        content = init_py_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return symbol_map

    base_dir = init_py_path.parent

    # Find all "from .xxx.yyy import" patterns (including multiline)
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"\s*from\s+(\.[a-zA-Z0-9_.]+)\s+import\s+", line)

        if match:
            module_path_str = match.group(1)  # e.g., ".common.taxonomy_core_vo"
            symbols_str = line[match.end() :]  # rest of line after "import "

            # If there's a closing paren, collect until it (multiline import)
            if "(" in symbols_str:
                depth = symbols_str.count("(") - symbols_str.count(")")
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    symbols_str += "\n" + lines[i]
                    depth = symbols_str.count("(") - symbols_str.count(")")

            # Resolve the module file
            clean_path = module_path_str[1:]  # strip leading "."
            parts = clean_path.split(".")
            current = base_dir

            for part in parts:
                candidate_py = current / f"{part}.py"
                if candidate_py.is_file():
                    source_file = candidate_py
                    break
                candidate_dir = current / part
                if candidate_dir.is_dir():
                    init_py = candidate_dir / "__init__.py"
                    current = candidate_dir if init_py.is_file() else candidate_dir
                else:
                    source_file = None
                    break
            else:
                source_file = None

            # Parse symbols (handle multiline imports)
            imported_symbols = set()
            for sym_line in symbols_str.split("\n"):
                for sym in sym_line.split(","):
                    sym = sym.strip()
                    if sym and not sym.startswith("("):
                        imported_symbols.add(sym)

            # Map each symbol to the source file
            for sym in imported_symbols:
                if source_file and sym not in symbol_map:
                    symbol_map.setdefault(sym, []).append(source_file)

        i += 1

    return symbol_map


def _resolve_init_py_imports(
    init_py_path: Path,
    base_dir: Path,
    max_depth: int = 5,
    required_symbols: set[str] | None = None,
) -> set[Path]:
    """Resolve transitive imports from an __init__.py file.

    If `required_symbols` is provided, only resolve files that contain
    those symbols (avoids pulling in unused shared modules).
    """
    resolved: set[Path] = {init_py_path}
    frontier: set[Path] = {init_py_path}

    rel_import_pattern = re.compile(r"\b(?:from|import)\s+(\.[a-zA-Z0-9_.]+)")

    symbol_map = {}
    if required_symbols:
        symbol_map = _extract_init_py_symbols(init_py_path)

    for _depth in range(max_depth):
        if not frontier:
            break
        next_frontier: set[Path] = set()
        for f in frontier:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for match in rel_import_pattern.finditer(content):
                module_path_str = match.group(1)  # e.g., ".common.taxonomy_core_vo"
                clean_path = module_path_str[1:]  # strip leading "."
                parts = clean_path.split(".")

                # If we have required_symbols, check if this module file is needed
                if required_symbols and symbol_map:
                    needed = False
                    for sym, files in symbol_map.items():
                        for sf in files:
                            rel = str(sf.relative_to(base_dir))
                            module_rel = clean_path.replace(".", "/")
                            if rel.endswith(f"{module_rel}.py") or rel == f"{module_rel}" and sym in required_symbols:
                                needed = True
                                break
                        if needed:
                            break
                    if not needed:
                        continue

                # Try to find the file — walk through path parts
                current = f.parent
                for _i, part in enumerate(parts):
                    candidate_py = current / f"{part}.py"
                    if candidate_py.is_file():
                        if candidate_py not in resolved:
                            resolved.add(candidate_py)
                            next_frontier.add(candidate_py)
                        break

                    candidate_dir = current / part
                    if candidate_dir.is_dir():
                        init_py = candidate_dir / "__init__.py"
                        if init_py.is_file():
                            if init_py not in resolved:
                                resolved.add(init_py)
                                next_frontier.add(init_py)
                            current = candidate_dir
                        else:
                            current = candidate_dir

        frontier = next_frontier

    return resolved


def _wildcard_import_pattern() -> re.Pattern[str]:
    """Return compiled pattern for multiline wildcard imports."""
    return re.compile(r"\bfrom\s+modules\.shared\.(src(?:\.[a-zA-Z0-9_]+)*)\s+import\s+\(([^)]+)\)")


def _relative_path(path: Path, root: Path) -> Path:
    """Return path relative to root if possible."""
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def write_markdown(
    output_path: Path,
    sorted_files: list[Path],
    workspace_root: Path,
    selected_module: str,
    safe_version: str,
) -> None:
    """Write consolidated Markdown document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# Module: {selected_module} (v{safe_version})\n\n")
        out.write(
            f"This document contains the source code for module `{selected_module}` "
            f"along with related and imported definitions from the `shared` module.\n\n"
        )

        out.write("## File List\n\n")
        for f in sorted_files:
            rel = _relative_path(f, workspace_root)
            rel_posix = rel.as_posix()
            out.write(f"- [{rel_posix}](<{rel_posix}>)\n")
        out.write("\n---\n\n")

        for f in sorted_files:
            rel = _relative_path(f, workspace_root)
            out.write(f"## File: {rel.as_posix()}\n\n")

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                content = f"/* Error reading file: {e} */\n"

            fence = _code_fence(content)
            lang = _language_for(f)

            out.write(f"{fence}{lang}\n")
            out.write(content)

            if not content.endswith("\n"):
                out.write("\n")

            out.write(f"{fence}\n\n---\n\n")


def export_module(
    workspace_root: Path,
    modules_dir: Path,
    selected_module: str,
    output: Path | None = None,
) -> Path:
    """Export one module to a consolidated Markdown file."""
    print(f"Processing module: {selected_module}...")

    module_path = modules_dir / selected_module

    version = read_version(workspace_root)
    safe_version = sanitize_version(version)
    print(f"Version resolved: {version} (filename-safe: {safe_version})")

    shared_src_dir = modules_dir / "shared" / "src"
    symbol_to_files = index_shared_symbols(shared_src_dir)

    files_to_export = collect_module_files(module_path, workspace_root)

    # Use AST-based transitive resolution for shared dependencies
    files_to_export = expand_shared_dependencies(files_to_export, shared_src_dir, symbol_to_files)

    default_name = f"{selected_module}_v{safe_version}.md"

    if output is None:
        output = workspace_root / ".agents" / "finding" / default_name
    else:
        output = output.expanduser()
        if output.is_dir():
            output = output / default_name

    output.parent.mkdir(parents=True, exist_ok=True)

    sorted_files = sorted(
        files_to_export,
        key=lambda p: _relative_path(p, workspace_root).as_posix().lower(),
    )

    print(f"Writing export to {output}...")
    write_markdown(output, sorted_files, workspace_root, selected_module, safe_version)

    return output


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for module selection and output path."""
    parser = argparse.ArgumentParser(description="Export a module into a single consolidated Markdown file.")
    parser.add_argument(
        "--module",
        "-m",
        help="Module name to export (non-interactive mode). Omit for interactive selection.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: .agents/finding/<module>_v<ver>.md).",
    )
    return parser.parse_args()


def main() -> None:
    """Export a module to Markdown, interactively or from CLI arguments."""
    args = parse_args()

    workspace_root, modules_dir = resolve_workspace()
    modules = list_modules(modules_dir)

    # Non-interactive CLI mode.
    if args.module:
        if args.module not in modules:
            print(
                f"Error: Module '{args.module}' not found. Available: {', '.join(modules)}",
                file=sys.stderr,
            )
            sys.exit(1)

        output = Path(args.output) if args.output else None
        output_path = export_module(workspace_root, modules_dir, args.module, output)
        print(f"\nSuccess! Consolidated Markdown file created: {output_path}")
        return

    # Interactive mode.
    if not modules:
        print("Error: No modules found in 'modules' directory.", file=sys.stderr)
        sys.exit(1)

    while True:
        print("\n=== Module Exporter ===")

        selected_module = prompt_module(modules)

        output_path = export_module(workspace_root, modules_dir, selected_module)
        print(f"\nSuccess! Consolidated Markdown file created: {output_path}")

        try:
            again = input("\nExport another module? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if again != "y":
            break

    print("Done.")


if __name__ == "__main__":
    main()
