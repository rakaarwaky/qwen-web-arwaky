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


def _is_excluded(path: Path) -> bool:
    """Return True if the path is inside an excluded directory."""
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


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
            if _is_excluded(entry):
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
        rel = f.relative_to(folder_path).as_posix()
        lines.append(f"- `{rel}`\n")
    lines.append("\n---\n\n")

    for f in files:
        rel = f.relative_to(folder_path).as_posix()
        lines.append(f"## {rel}\n\n")

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
    "compile_files_to_markdown",
    "validate_folder_for_compile",
]
