"""Utility: folder-to-markdown compiler (pure functions).

Taxonomy layer (utility): stateless functions, taxonomy imports only.
Collects code/md files from a folder and compiles them into a single markdown file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import CODE_EXTENSIONS, EXCLUDED_DIR_NAMES, MAX_FOLDER_DEPTH
from modules.shared.src.taxonomy_core_error import FolderEmptyError, FolderValidationError


def _is_excluded(path: Path, root: Path) -> bool:
    """Return True if the path is inside an excluded directory below ``root``.

    Only components below the scan root are inspected so that a project under
    an ancestor directory named ``build``/``dist``/``venv`` etc. is not
    rejected wholesale.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part in EXCLUDED_DIR_NAMES for part in relative.parts)


def _is_text_file(filepath: Path) -> bool:
    """Check if a file is a text file by trying to read a small chunk."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" not in chunk
    except (OSError, PermissionError):
        return False


def collect_folder_files(
    folder_path: Path,
    max_depth: int = MAX_FOLDER_DEPTH,
    include_extensions: frozenset[str] | None = None,
) -> list[Path]:
    """Collect text files from folder recursively.

    Args:
        folder_path: Root folder to scan.
        max_depth: Maximum recursion depth (default: 5).
        include_extensions: File extensions to include (default: CODE_EXTENSIONS).

    Returns:
        Sorted list of file paths.

    Raises:
        FolderValidationError: If folder_path is invalid.
    """
    if include_extensions is None:
        include_extensions = CODE_EXTENSIONS

    if not isinstance(folder_path, (str, Path)):
        raise FolderValidationError(f"Invalid path: {folder_path}")

    folder_path = Path(folder_path)

    if not folder_path.exists():
        raise FolderValidationError(f"Folder does not exist: {folder_path}")
    if not folder_path.is_dir():
        raise FolderValidationError(f"Path is not a directory: {folder_path}")
    if not os.access(folder_path, os.R_OK):
        raise FolderValidationError(f"Folder is not readable: {folder_path}")

    files: list[Path] = []

    def _scan(current: Path, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return

        for entry in entries:
            if _is_excluded(entry, folder_path):
                continue

            if entry.is_file():
                ext = entry.suffix.lower()
                if ext in include_extensions and _is_text_file(entry):
                    files.append(entry)
            elif entry.is_dir():
                _scan(entry, depth + 1)

    _scan(folder_path, 0)
    return sorted(files, key=lambda p: str(p.relative_to(folder_path)).lower())


def _language_for(filepath: Path) -> str:
    """Pick a fenced-code-block language identifier based on file extension."""
    ext_map = {
        ".py": "python",
        ".rs": "rust",
        ".ts": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".cfg": "ini",
        ".md": "markdown",
        ".txt": "",
        ".css": "css",
        ".scss": "scss",
        ".html": "html",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
    }
    return ext_map.get(filepath.suffix.lower(), "")


def _code_fence(content: str) -> str:
    """Return a Markdown fence long enough not to collide with content."""
    runs = re.findall(r"`+", content)
    longest = max((len(run) for run in runs), default=0)
    return "`" * max(3, longest + 1)


def compile_files_to_markdown(
    files: list[Path],
    folder_path: Path,
    title: str | None = None,
    origins: dict[Path, tuple[str, ...]] | None = None,
) -> str:
    """Compile a list of files into a single markdown document.

    Args:
        files: List of file paths to compile.
        folder_path: Root folder path (used for relative paths in output).
        title: Optional title for the markdown document.

    Returns:
        Compiled markdown content.

    Raises:
        FolderEmptyError: If files list is empty.
    """
    if not files:
        raise FolderEmptyError("No files to compile")

    if title is None:
        title = folder_path.name

    lines: list[str] = []
    lines.append(f"# {title}\n\n")
    lines.append(f"Compiled from `{folder_path.as_posix()}` ({len(files)} files)\n\n")

    lines.append("## File List\n\n")
    for f in files:
        rel = _display_rel(f, folder_path)
        origin = ""
        if origins and origins.get(f):
            origin = f" *(imported by {', '.join(origins[f])})*"
        lines.append(f"- `{rel}`{origin}\n")
    lines.append("\n---\n\n")

    for f in files:
        rel = _display_rel(f, folder_path)
        origin = ""
        if origins and origins.get(f):
            origin = f" *(imported by {', '.join(origins[f])})*"
        lines.append(f"## {rel}{origin}\n\n")

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError) as e:
            content = f"/* Error reading file: {e} */\n"

        fence = _code_fence(content)
        lang = _language_for(f)

        lines.append(f"{fence}{lang}\n")
        lines.append(content)
        if not content.endswith("\n"):
            lines.append("\n")
        lines.append(f"{fence}\n\n---\n\n")

    return "".join(lines)


def _display_rel(path: Path, folder_path: Path) -> str:
    """Return a display path relative to the folder root (../ for external files)."""
    try:
        return path.relative_to(folder_path).as_posix()
    except ValueError:
        return Path(os.path.relpath(path, folder_path)).as_posix()


# ─── Import resolution (multi-language) ─────────────────────────────────────

_IMPORTABLE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",
        ".hxx",
        ".hh",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".sh",
        ".bash",
        ".zsh",
    }
)

_TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_TS_INDEX_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs")

_PY_MODULE = re.compile(r"^\s*(?:from\s+([.\w]+)\s+import\s+[\w,*\s]+|import\s+([.\w]+))", re.MULTILINE)
_JS_IMPORT = re.compile(
    r"""(?:import|export)\s+[^'"']*?from\s*['"']([^'"']+)['"']"""
    r"""|import\s*['"']([^'"']+)['"']"""
    r"""|require\s*\(\s*['"']([^'"']+)['"']\s*\)""",
    re.MULTILINE,
)
_C_INCLUDE = re.compile(r"^\s*#\s*include\s+\"([^\"]+)\"", re.MULTILINE)
_GO_IMPORT = re.compile(r"^\s*import\s+(?:[.\w]+\s+)?\"([^\"]+)\"", re.MULTILINE)
_RUST_MOD = re.compile(r"^\s*mod\s+([\w]+)\s*;", re.MULTILINE)
_RUST_USE = re.compile(r"^\s*use\s+(?:crate::|super::)?([\w:]+)", re.MULTILINE)
_PHP_INCLUDE = re.compile(
    r"""^\s*(?:require|require_once|include|include_once)\s*\(\s*['"']([^'"']+)['"']\s*\)\s*;"""
    r"""|^\s*(?:require|require_once|include|include_once)\s+['"']([^'"']+)['"']\s*;""",
    re.MULTILINE,
)
_RUBY_REQUIRE = re.compile(
    r"""^\s*require_relative\s+['"']([^'"']+)['"']|^\s*require\s+['"']([^'"']+)['"']""",
    re.MULTILINE,
)
_SHELL_SOURCE = re.compile(r"^\s*(?:source|\.)\s+([^\s;#]+)", re.MULTILINE)


def _parse_imports(filepath: Path) -> list[str]:
    """Parse local import/reference specifiers from a source file (multi-language).

    Only specifiers that can plausibly point at local files are returned;
    external packages/stdlib resolve to nothing during lookup and are skipped.
    """
    suffix = filepath.suffix.lower()
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []
    specs: list[str] = []
    if suffix == ".py":
        for m in _PY_MODULE.finditer(content):
            spec = m.group(1) or m.group(2)
            if spec:
                specs.append(spec)
    elif suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        for m in _JS_IMPORT.finditer(content):
            spec = next((g for g in m.groups() if g), None)
            if spec:
                specs.append(spec)
    elif suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"):
        specs.extend(_C_INCLUDE.findall(content))
    elif suffix == ".go":
        specs.extend(_GO_IMPORT.findall(content))
    elif suffix == ".rs":
        for m in _RUST_MOD.finditer(content):
            specs.append(f"mod:{m.group(1)}")
        for m in _RUST_USE.finditer(content):
            specs.append(f"use:{m.group(1)}")
    elif suffix == ".php":
        for m in _PHP_INCLUDE.finditer(content):
            spec = next((g for g in m.groups() if g), None)
            if spec:
                specs.append(spec)
    elif suffix == ".rb":
        for m in _RUBY_REQUIRE.finditer(content):
            spec = next((g for g in m.groups() if g), None)
            if spec:
                specs.append(spec)
    elif suffix in (".sh", ".bash", ".zsh"):
        specs.extend(_SHELL_SOURCE.findall(content))
    return specs


def _py_candidates(base_dir: Path, folder_path: Path, spec: str) -> list[Path]:
    """Python candidates: ``a.b`` -> a/b.py | a/b/__init__.py; ``.a``/``..a`` relative."""
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        mod = spec.lstrip(".")
        rel_dir = base_dir
        for _ in range(dots - 1):
            rel_dir = rel_dir.parent
        if not mod:
            return [rel_dir / "__init__.py"]
        parts = Path(*mod.split("."))
        return [rel_dir / parts.with_suffix(".py"), rel_dir / parts / "__init__.py"]
    parts = Path(*spec.split("."))
    cands: list[Path] = []
    # Resolve against the common project root (parent of the scanned folder),
    # the scanned folder itself, and the importing file's directory.
    for root in (folder_path.parent, folder_path, base_dir):
        cands.append(root / parts.with_suffix(".py"))
        cands.append(root / parts / "__init__.py")
    return cands


def _ts_candidates(base_dir: Path, spec: str) -> list[Path]:
    """JS/TS candidates: relative specs only; bare names resolve to node_modules."""
    if not (spec.startswith("./") or spec.startswith("../")):
        return []
    base = (base_dir / spec).resolve()
    if base.suffix:
        return [base]
    cands: list[Path] = [base.with_suffix(ext) for ext in _TS_EXTS]
    cands.extend(base / f"index{ext}" for ext in _TS_INDEX_EXTS)
    return cands


def _c_candidates(base_dir: Path, spec: str) -> list[Path]:
    """C/C++ candidates: quote includes resolve relative to the including file."""
    base = base_dir / spec
    if base.suffix:
        return [base]
    return [base, base.with_suffix(".h"), base.with_suffix(".hpp"), base.with_suffix(".c"), base.with_suffix(".cpp")]


def _go_candidates(base_dir: Path, folder_path: Path, spec: str) -> list[Path]:
    """Go candidates: relative imports plus direct module-path mapping under root."""
    if spec.startswith("./") or spec.startswith("../"):
        base = (base_dir / spec).resolve()
        return [base] if base.suffix else [base.with_suffix(".go"), base / "main.go"]
    base = folder_path / spec
    return [base] if base.suffix else [base.with_suffix(".go"), base / "main.go"]


def _rust_candidates(base_dir: Path, folder_path: Path, spec: str) -> list[Path]:
    """Rust candidates: ``mod x`` and ``use crate::a::b`` relative to crate root."""
    if spec.startswith("mod:"):
        name = spec[4:]
        return [
            base_dir / f"{name}.rs",
            base_dir / name / "mod.rs",
            folder_path / f"{name}.rs",
            folder_path / name / "mod.rs",
        ]
    parts = spec[4:].split("::")  # strip "use:"
    cands: list[Path] = []
    for i in range(1, len(parts) + 1):
        rel = Path(*parts[:i])
        cands.append(folder_path / rel.with_suffix(".rs"))
        cands.append(folder_path / rel / "mod.rs")
    return cands


def _php_candidates(base_dir: Path, spec: str) -> list[Path]:
    base = base_dir / spec
    if base.suffix:
        return [base]
    return [base.with_suffix(".php"), base / "index.php"]


def _ruby_candidates(base_dir: Path, spec: str) -> list[Path]:
    base = base_dir / spec
    if base.suffix:
        return [base]
    return [base.with_suffix(".rb"), base / "index.rb"]


def _shell_candidates(base_dir: Path, spec: str) -> list[Path]:
    base = base_dir / spec
    if base.suffix:
        return [base]
    return [base, base.with_suffix(".sh"), base.with_suffix(".bash")]


def _resolve_import(filepath: Path, spec: str, folder_path: Path) -> Path | None:
    """Resolve one import specifier to an existing local file, or None."""
    suffix = filepath.suffix.lower()
    base_dir = filepath.parent
    cands: list[Path] = []
    if suffix == ".py":
        cands = _py_candidates(base_dir, folder_path, spec)
    elif suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        cands = _ts_candidates(base_dir, spec)
    elif suffix in (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"):
        cands = _c_candidates(base_dir, spec)
    elif suffix == ".go":
        cands = _go_candidates(base_dir, folder_path, spec)
    elif suffix == ".rs":
        cands = _rust_candidates(base_dir, folder_path, spec)
    elif suffix == ".php":
        cands = _php_candidates(base_dir, spec)
    elif suffix == ".rb":
        cands = _ruby_candidates(base_dir, spec)
    elif suffix in (".sh", ".bash", ".zsh"):
        cands = _shell_candidates(base_dir, spec)
    for cand in cands:
        try:
            if cand.is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def collect_folder_files_with_imports(
    folder_path: Path,
    max_depth: int = MAX_FOLDER_DEPTH,
    import_depth: int = 3,
) -> tuple[list[Path], dict[Path, tuple[str, ...]]]:
    """Collect in-folder files plus files they import from outside the folder.

    Imports are parsed per language (Python, JS/TS, C/C++, Go, Rust, PHP,
    Ruby, shell) and resolved relative to the importing file (and the folder
    root where the language allows). External dependencies are included
    recursively with cycle protection, up to ``import_depth`` hops.

    Returns:
        ``(files, origins)``: ordered list to compile and a mapping of each
        external file to the display names of its importers (in-folder files
        map to an empty tuple).

    Raises:
        FolderValidationError: If the folder is invalid.
        FolderEmptyError: If the folder contains no compilable files.
    """
    folder_path = Path(folder_path).resolve()
    base_files = validate_folder_for_compile(folder_path, max_depth=max_depth)
    files: list[Path] = list(base_files)
    origins: dict[Path, tuple[str, ...]] = {f: () for f in base_files}
    seen: set[Path] = set(files)
    frontier: list[Path] = list(files)
    for _ in range(import_depth):
        next_frontier: list[Path] = []
        for f in frontier:
            for spec in _parse_imports(f):
                resolved = _resolve_import(f, spec, folder_path)
                if resolved is None or resolved in seen:
                    continue
                if resolved.suffix.lower() not in _IMPORTABLE_SUFFIXES:
                    continue
                # External files: skip imports living inside excluded
                # directories (node_modules, build, dist, venv, ...).
                if any(part in EXCLUDED_DIR_NAMES for part in resolved.parts):
                    continue
                seen.add(resolved)
                next_frontier.append(resolved)
                importer = _display_rel(f, folder_path)
                merged = (*origins.get(resolved, ()), importer)
                origins[resolved] = tuple(dict.fromkeys(merged))
        if not next_frontier:
            break
        frontier = next_frontier
        files.extend(next_frontier)
    return files, origins


def validate_folder_for_compile(folder_path: Path, max_depth: int = MAX_FOLDER_DEPTH) -> list[Path]:
    """Validate folder and return collected files.

    Args:
        folder_path: Folder to validate and scan.
        max_depth: Maximum recursion depth.

    Returns:
        List of files found.

    Raises:
        FolderValidationError: If folder is invalid.
        FolderEmptyError: If no compilable files found.
    """
    files = collect_folder_files(folder_path, max_depth=max_depth)
    if not files:
        raise FolderEmptyError(
            f"No compilable files found in {folder_path}. Supported extensions: {', '.join(sorted(CODE_EXTENSIONS))}"
        )
    return files


__all__ = [
    "collect_folder_files",
    "collect_folder_files_with_imports",
    "compile_files_to_markdown",
    "validate_folder_for_compile",
]
