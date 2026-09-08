#!/usr/bin/env python3
"""Export a selected source file into a single consolidated Markdown document.

The output includes the selected file's content, its transitive dependencies
(imported files from ``import`` / ``from ... import`` statements), and related
documentation (ARCHITECTURE.md, PRD.md, FRD of the owning module, relevant
skill files in .agents/skills/).

Usage:
    # Interactive mode (prompts for selection):
    python3 scripts/export/export_file.py

    # CLI mode (non-interactive):
    python3 scripts/export/export_file.py --file modules/gateway/src/capabilities_blender_command_adapter.py
    python3 scripts/export/export_file.py --file modules/telemetry/src/agent_orchestrator.py --output /tmp/out.md
"""

import argparse
import re
import sys
from pathlib import Path

# Sanitize version strings to a safe filename fragment (CWE-22 mitigation).
SAFE_VERSION_CHARS = re.compile(r"[^0-9A-Za-z.\-]")

# ---------------------------------------------------------------------------
# File discovery & selection (ranger-style numbered navigation)
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".rs", ".py", ".js", ".ts", ".jsx", ".tsx"}


def resolve_project_root() -> Path:
    """Return the project root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def discover_source_files(project_root: Path) -> list[Path]:
    """Recursively find all source files with supported extensions."""
    sources: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        sources.extend(sorted(project_root.rglob(f"*{ext}")))
    # Filter out target/, build/, .git, node_modules, virtualenvs, etc.
    filtered: list[Path] = []
    for f in sources:
        parts = f.parts
        if any(skip in parts for skip in (".git", "target", "node_modules")):
            continue
        # Skip binary / generated files (keep .rs, .py, .js, .ts, .jsx, .tsx)
        filtered.append(f)
    return sorted(filtered)


def _rel_display(path: Path, project_root: Path) -> str:
    """Return a relative path string for display."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def prompt_file(_sources: list[Path]) -> Path:
    """Prompt user to type or paste the file path to export.

    Supports:
      - Paste full path (e.g. modules/gateway/src/capabilities_blender_command_adapter.py)
      - Type relative path from project root
      - Drag-and-drop (shell expands to full path)
      - Tab completion if available
    """
    while True:
        try:
            path = input("Paste or type the file path to export (q to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)

        if path.lower() == "q":
            print("Exiting.")
            sys.exit(0)

        # Try as absolute or relative path
        file_path = Path(path)

        # Resolve ~ and env vars
        file_path = file_path.expanduser()

        # Convert to absolute (handles both relative and absolute paths)
        file_path = file_path.resolve()

        if file_path.is_file():
            return file_path

        print(f"Error: File not found — '{path}'")


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

# Rust: `use modules::foo::bar` or `from modules.shared import baz`
RUST_USE_PATTERN = re.compile(r"\b(?:use|from)\s+(modules|shared)::([a-zA-Z0-9_:]+)")
# Python: `import foo.bar` or `from foo.bar import baz`
PYTHON_IMPORT_PATTERN = re.compile(r"^(?:import|from)\s+([a-zA-Z0-9_.]+)", re.MULTILINE)


def _to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case for file matching."""
    result = ""
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            result += "_"
        result += c.lower()
    return result


def extract_dependencies(file_path: Path, content: str) -> list[dict]:
    """Extract dependency module paths from source file.

    Returns list of dicts with 'source' (rust/modules/shared/python) and
    'segments' (list of path parts).
    """
    deps: list[dict] = []
    suffix = file_path.suffix

    if suffix == ".rs":
        for m in RUST_USE_PATTERN.finditer(content):
            source = m.group(1)  # "modules" or "shared"
            path_str = m.group(2)  # e.g., "server::contract_command_protocol::ICommandProtocol"
            parts = path_str.split("::")
            segments: list[str] = []
            for p in parts:
                s = _to_snake(p)
                segments.append(s)
            if segments:
                deps.append({"source": source, "segments": segments})
    elif suffix == ".py":
        for m in PYTHON_IMPORT_PATTERN.finditer(content):
            module = m.group(1)
            # Only track modules under modules/ or shared/
            if module.startswith("modules.") or module.startswith("shared."):
                deps.append({"source": "python", "segments": module.split(".")})

    return deps


def resolve_dependency_path(dep: dict, file_path: Path, project_root: Path) -> set[Path]:
    """Try to locate the actual file that `dep` refers to.

    Handles Rust imports (modules:: and shared::), Python imports, and nested modules.
    """
    found: set[Path] = set()
    source = dep.get("source", "")
    segments = dep.get("segments", [])
    if not segments:
        return found

    # Build candidate paths from segments (try progressively shorter suffixes)
    candidates: list[list[str]] = []
    for i in range(len(segments)):
        candidates.append(segments[i:])

    if source == "shared":
        # shared module: search in modules/shared/src/<module>/.../*.py
        shared_src = project_root / "modules" / "shared" / "src"
        if not shared_src.exists():
            return found

        for segs in candidates:
            base = shared_src
            for _i, seg in enumerate(segs):
                # Try both underscore and dash variants for directory names
                dir_candidates = [seg]
                if "_" in seg:
                    dir_candidates.append(seg.replace("_", "-"))
                if "-" in seg:
                    dir_candidates.append(seg.replace("-", "_"))

                # First: try as .py file (individual module)
                candidate_file = base / f"{seg}.py"
                if candidate_file.is_file():
                    found.add(candidate_file)
                    continue  # keep trying next segment

                # Second: try as directory (recurse)
                found_dir = None
                for dc in dir_candidates:
                    candidate_dir = base / dc
                    if candidate_dir.is_dir():
                        found_dir = candidate_dir
                        break

                if found_dir is not None:
                    base = found_dir
                    # Try file match at this level (__init__.py or mod.py)
                    init_py = base / "__init__.py"
                    if init_py.is_file():
                        found.add(init_py)
                    continue

                # Neither .py file nor directory — path is broken
                break

    elif source == "modules":
        # modules-local: search in modules/<crate>/src/...
        try:
            rel = file_path.relative_to(project_root / "modules")
        except ValueError:
            return found
        module_dir = project_root / "modules" / rel.parts[0] / "src"

        for segs in candidates:
            base = module_dir
            for _i, seg in enumerate(segs):
                # First: try as .py file (individual module)
                candidate_file = base / f"{seg}.py"
                if candidate_file.is_file():
                    found.add(candidate_file)
                    continue  # keep trying next segment

                # Second: try as directory (recurse)
                candidate_dir = base / seg
                if candidate_dir.is_dir():
                    base = candidate_dir
                    init_py = base / "__init__.py"
                    if init_py.is_file():
                        found.add(init_py)
                    continue

                # Neither .py file nor directory — path is broken
                break

    elif source == "python":
        # Python: look in modules/, same directory, __init__.py parents
        # e.g., modules.gateway.src.capabilities -> modules/gateway/src/
        search_bases = [project_root / "modules"]

        for base in search_bases:
            if not base.exists():
                continue

            for segs in candidates:
                current = base
                matched_file = None
                for seg in segs:
                    # Try as .py file — exact module file wins.
                    candidate_py = current / f"{seg}.py"
                    if candidate_py.is_file():
                        matched_file = candidate_py
                        break

                    # Continue into directory
                    candidate_dir = current / seg
                    if candidate_dir.is_dir():
                        current = candidate_dir
                    else:
                        break

                if matched_file is not None:
                    found.add(matched_file)
                else:
                    # Segment chain exhausted on a directory — that is a
                    # package; record its __init__.py when present.
                    init_py = current / "__init__.py"
                    if init_py.is_file():
                        found.add(init_py)

    return found


def resolve_transitive_dependencies(
    initial_deps: set[Path],
    project_root: Path,
    max_depth: int = 3,
) -> set[Path]:
    """Resolve dependencies of dependencies up to `max_depth` levels."""
    resolved: set[Path] = set(initial_deps)
    frontier: set[Path] = set(initial_deps)

    for _ in range(max_depth):
        if not frontier:
            break
        next_frontier: set[Path] = set()
        for f in frontier:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            deps = extract_dependencies(f, content)
            for dep in deps:
                new_files = resolve_dependency_path(dep, f, project_root)
                for nf in new_files:
                    if nf not in resolved:
                        resolved.add(nf)
                        next_frontier.add(nf)
        frontier = next_frontier

    return resolved


# ---------------------------------------------------------------------------
# Documentation & skill matching
# ---------------------------------------------------------------------------


def find_frd_for_file(file_path: Path, project_root: Path) -> set[Path]:
    """Find FRD.md for the module that owns this file."""
    frds: set[Path] = set()
    modules_dir = project_root / "modules"

    if not modules_dir.exists():
        return frds

    # Check if file is inside a module directory
    try:
        rel = file_path.relative_to(modules_dir)
    except ValueError:
        return frds  # Not under modules/

    # Get the module name (first segment)
    module_name = rel.parts[0]
    frd_path = modules_dir / module_name / "FRD.md"
    if frd_path.is_file():
        frds.add(frd_path)

    return frds


def find_relevant_skills(file_path: Path, skills_dir: Path) -> set[Path]:
    """Find all .md files in the matched skill directory based on file prefix/pattern.

    When user selects a source file, automatically match the filename prefix
    to the corresponding skill directory and include ALL .md files from it.

    Examples:
        capabilities_check_bypass_checker.py → create-capabilities-python/*.md
        agent_analysis_pipeline_orchestrator.py → create-agent-python/*.md
        surface_check_command.py → create-surface-python/*.md

    Includes SKILL.md, references/*.md, templates/*.md, evals/*.md, etc.
    """
    skills: set[Path] = set()
    if not skills_dir.exists():
        return skills

    stem = file_path.stem  # e.g., "capabilities_check_bypass_checker"

    # Map known layer prefixes to skill names
    prefix_to_skill = {
        "capabilities": "create-capabilities",
        "agent": "create-agent",
        "contract": "create-contract",
        "taxonomy": "create-taxonomy",
        "surface": "create-surface",
        "root": "create-root",
    }

    # Determine language suffix from file extension
    ext = file_path.suffix
    if ext == ".py":
        lang_suffix = "-python"
    elif ext == ".rs":
        lang_suffix = "-rust"
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        lang_suffix = "-typescript"
    else:
        return skills

    # Check if stem starts with any known prefix
    for prefix, skill_base in prefix_to_skill.items():
        if stem.startswith(f"{prefix}_") or stem == prefix:
            skill_name = f"{skill_base}{lang_suffix}"
            skill_path = skills_dir / skill_name

            # Collect ALL .md files from the matched skill directory (recursively)
            if skill_path.is_dir():
                for md_file in skill_path.rglob("*.md"):
                    if md_file.is_file():
                        skills.add(md_file)

    return skills


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def _language_for(path: Path) -> str:
    """Pick a fenced-code-block language identifier based on file extension."""
    if path.name == "pyproject.toml":
        return "toml"
    if path.suffix in (".py",):
        return "python"
    if path.suffix in (".rs",):
        return "rust"
    if path.suffix in (".js", ".ts", ".jsx", ".tsx"):
        return "typescript"
    if path.suffix == ".md":
        return "markdown"
    if path.suffix in (".yaml", ".yml"):
        return "yaml"
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".toml":
        return "toml"
    return ""


def write_markdown(
    output_path: Path,
    selected_file: Path,
    dependency_files: set[Path],
    project_root: Path,
    related_docs: set[Path],
) -> None:
    """Write the consolidated Markdown document."""
    all_files = sorted(dependency_files | related_docs)

    with open(output_path, "w", encoding="utf-8") as out:
        # Header
        rel = selected_file.relative_to(project_root)
        out.write(f"# Export: {rel}\n\n")
        out.write(
            f"This document contains the source code for `{rel}` "
            f"along with its resolved dependencies and related documentation.\n\n"
        )

        # File list
        out.write("## File List\n\n")
        out.write("**Selected file:**\n")
        out.write(f"- [{rel}]({selected_file.as_uri()})\n\n")

        if all_files:
            out.write("**Dependencies & related docs:**\n")
            for f in all_files:
                try:
                    rel_f = f.relative_to(project_root)
                except ValueError:
                    rel_f = f
                out.write(f"- [{rel_f}]({f.as_uri()})\n")
        out.write("\n---\n\n")

        # Selected file content (always first)
        out.write(f"## Selected File: {rel}\n\n")
        lang = _language_for(selected_file)
        out.write(f"```{lang}\n")
        try:
            content = selected_file.read_text(encoding="utf-8", errors="replace")
            escaped = content.replace("```", "``` `")
            out.write(escaped)
            if not content.endswith("\n"):
                out.write("\n")
        except OSError as e:
            out.write(f"/* Error reading file: {e} */\n")
        out.write("```\n\n---\n\n")

        # Dependency files
        for f in all_files:
            try:
                rel_f = f.relative_to(project_root)
            except ValueError:
                rel_f = f

            out.write(f"## File: {rel_f}\n\n")
            lang = _language_for(f)
            out.write(f"```{lang}\n")
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                escaped = content.replace("```", "``` `")
                out.write(escaped)
                if not content.endswith("\n"):
                    out.write("\n")
            except OSError as e:
                out.write(f"/* Error reading file: {e} */\n")
            out.write("```\n\n---\n\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a source file into a single consolidated Markdown document.")
    parser.add_argument(
        "--file",
        "-f",
        help="Source file path to export (non-interactive mode). Omit for interactive selection.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: .agents/finding/<stem>_export.md).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Capture via getattr: Pylance false-positives on synthesized Namespace.__getattr__ for plain attribute access.
    file_arg: str | None = getattr(args, "file", None)
    output_arg: str | None = getattr(args, "output", None)

    if file_arg:
        # Non-interactive CLI mode
        project_root = resolve_project_root()
        skills_dir = project_root / ".agents" / "skills"

        selected_file = Path(file_arg)
        if not selected_file.is_absolute():
            selected_file = project_root / selected_file
        if not selected_file.is_file():
            print(f"Error: File not found: {file_arg}", file=sys.stderr)
            sys.exit(1)

        rel = selected_file.relative_to(project_root)
        print(f"Processing: {rel}")

        try:
            content = selected_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Error: Cannot read file ({e})", file=sys.stderr)
            sys.exit(1)

        deps = extract_dependencies(selected_file, content)
        initial_deps: set[Path] = set()
        for dep in deps:
            initial_deps.update(resolve_dependency_path(dep, selected_file, project_root))

        print(f"Extracted {len(deps)} dependency reference(s), resolved to {len(initial_deps)} file(s).")

        transitive = resolve_transitive_dependencies(initial_deps, project_root)
        all_dep_files = (initial_deps | transitive) - {selected_file}
        print(f"Transitive resolution: {len(all_dep_files)} dependency file(s).")

        frds = find_frd_for_file(selected_file, project_root)
        skills = find_relevant_skills(selected_file, skills_dir)
        related_docs: set[Path] = set()

        arch_md = project_root / "ARCHITECTURE.md"
        prd_md = project_root / "PRD.md"
        if arch_md.is_file():
            related_docs.add(arch_md)
        if prd_md.is_file():
            related_docs.add(prd_md)

        related_docs.update(frds)
        related_docs.update(skills)
        print(f"Related docs: {len(frds)} FRD(s), {len(skills)} skill(s).")

        if output_arg:
            output_path = Path(output_arg)
        else:
            output_filename = f"{selected_file.stem}_export.md"
            output_path = project_root / ".agents" / "finding" / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Writing export to {output_path}...")
        write_markdown(
            output_path,
            selected_file,
            all_dep_files,
            project_root,
            related_docs,
        )

        print(f"\nSuccess! Consolidated markdown file created: {output_path}")
        return

    # Interactive mode
    while True:
        print("\n=== Blender MCP File Exporter ===")

        project_root = resolve_project_root()
        skills_dir = project_root / ".agents" / "skills"

        # Discover files
        sources = discover_source_files(project_root)
        if not sources:
            print("Error: No source files found.", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(sources)} source file(s).")

        # Prompt selection
        selected_file = prompt_file(sources)
        rel = selected_file.relative_to(project_root)
        print(f"\nSelected: {rel}")

        # Read file content
        try:
            content = selected_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Error: Cannot read file ({e})", file=sys.stderr)
            sys.exit(1)

        # Extract & resolve dependencies
        deps = extract_dependencies(selected_file, content)
        initial_deps: set[Path] = set()
        for dep in deps:
            initial_deps.update(resolve_dependency_path(dep, selected_file, project_root))

        print(f"Extracted {len(deps)} dependency reference(s), resolved to {len(initial_deps)} file(s).")

        # Resolve transitive dependencies
        transitive = resolve_transitive_dependencies(initial_deps, project_root)
        all_dep_files = (initial_deps | transitive) - {selected_file}
        print(f"Transitive resolution: {len(all_dep_files)} dependency file(s).")

        # Find related documentation (FRD + matching skills)
        frds = find_frd_for_file(selected_file, project_root)
        skills = find_relevant_skills(selected_file, skills_dir)
        related_docs: set[Path] = set()

        # Always include ARCHITECTURE.md and PRD.md at root level
        arch_md = project_root / "ARCHITECTURE.md"
        prd_md = project_root / "PRD.md"
        if arch_md.is_file():
            related_docs.add(arch_md)
        if prd_md.is_file():
            related_docs.add(prd_md)

        related_docs.update(frds)
        related_docs.update(skills)
        print(f"Related docs: {len(frds)} FRD(s), {len(skills)} skill(s).")

        # Write output
        output_filename = f"{selected_file.stem}_export.md"
        output_path = project_root / ".agents" / "finding" / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Writing export to {output_path}...")
        write_markdown(
            output_path,
            selected_file,
            all_dep_files,
            project_root,
            related_docs,
        )

        print(f"\nSuccess! Consolidated markdown file created: {output_path}")

        try:
            again = input("\nExport another file? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if again != "y":
            break

    print("Done.")


if __name__ == "__main__":
    main()
