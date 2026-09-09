"""Capabilities: folder-to-markdown compiler (AES403).

Implements IFolderCompileProtocol.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IFolderCompileProtocol
from modules.shared.src.taxonomy_core_constant import MAX_FOLDER_DEPTH
from modules.shared.src.taxonomy_core_error import FolderCompileError, FolderEmptyError, FolderValidationError
from modules.shared.src.utility_folder_compiler import (
    collect_folder_files_with_imports,
    compile_files_to_markdown,
    validate_folder_for_compile,
)

log = get_logger("capabilities_folder_compiler")


# ─── Block 1: Class Definition & Constructor ────────────
class FolderCompiler(IFolderCompileProtocol):
    """Compile folder contents into a single markdown file for attachment."""

    def __init__(self, input_dir: Path | None = None) -> None:
        """Initialize folder compiler.

        Args:
            input_dir: Directory to store compiled output. Defaults to .qwen-web/input/
        """
        if input_dir is not None:
            self.input_dir = input_dir
        else:
            self.input_dir = Path.cwd() / ".qwen-web" / "input"

    # ─── Block 2: Public Contract (IFolderCompileProtocol ONLY) ──
    def compile_folder(
        self,
        folder_path: Path,
        output_path: Path | None = None,
        max_depth: int = MAX_FOLDER_DEPTH,
        include_imports: bool = True,
    ) -> Path:
        """Compile folder contents to a single markdown file.

        When ``include_imports`` is enabled (default), files inside the folder
        are scanned for import/reference statements (Python, JS/TS, C/C++,
        Go, Rust, PHP, Ruby, shell) and files imported from outside the folder
        are resolved and included recursively, marked as ``(imported by ...)``.

        Args:
            folder_path: Directory to compile.
            output_path: Optional output file path. Auto-generated if None.
            max_depth: Maximum recursion depth.
            include_imports: Follow imports of folder files and include
                external dependencies (cycle-safe, bounded hops).

        Returns:
            Path to the compiled markdown file.

        Raises:
            FolderValidationError: If folder is invalid.
            FolderEmptyError: If no compilable files found.
            FolderCompileError: If compilation fails.
        """
        folder_path = Path(folder_path).resolve()
        log.info("Compiling folder: %s (max_depth=%d, include_imports=%s)", folder_path, max_depth, include_imports)

        try:
            if include_imports:
                files, origins = collect_folder_files_with_imports(folder_path, max_depth=max_depth)
                log.info("Found %d files (%d imported)", len(files), sum(1 for o in origins.values() if o))
            else:
                files = validate_folder_for_compile(folder_path, max_depth=max_depth)
                origins = None
                log.info("Found %d compilable files", len(files))
        except (FolderValidationError, FolderEmptyError) as e:
            log.error("Folder validation failed: %s", e)
            raise

        if output_path is None:
            output_path = self._generate_output_path(folder_path)

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            markdown_content = compile_files_to_markdown(files, folder_path, origins=origins)
            output_path.write_text(markdown_content, encoding="utf-8")
            log.info("Compiled markdown written to: %s", output_path)
            return output_path
        except (OSError, FolderEmptyError) as e:
            log.error("Failed to write compiled markdown: %s", e)
            raise FolderCompileError(f"Compilation failed: {e}") from e

    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""
        return Path(path).is_dir()

    # ─── Block 3: Private Helpers ──
    def _generate_output_path(self, folder_path: Path) -> Path:
        """Generate output path with timestamp: .qwen-web/input/{folder_name}_{timestamp}.md"""
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        folder_name = folder_path.name
        filename = f"{folder_name}_{timestamp}.md"
        return self.input_dir / filename


__all__ = ["FolderCompiler"]
