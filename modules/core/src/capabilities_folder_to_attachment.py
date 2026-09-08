"""Capabilities: folder-to-attachment adapter (AES403).

Bridges folder compiler with the upload flow.
Detects if path is folder or file, compiles folder if needed.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.capabilities_folder_compiler import FolderCompiler
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IFolderCompileProtocol
from modules.shared.src.taxonomy_core_constant import MAX_FOLDER_DEPTH
from modules.shared.src.taxonomy_core_error import FolderCompileError, FolderValidationError

log = get_logger("capabilities_folder_to_attachment")


# ─── Block 1: Class Definition & Constructor ────────────
class FolderToAttachmentAdapter:
    """Adapter that resolves path to attachment-ready file.

    If path is a folder, compile to markdown first.
    If path is a file, return as-is.
    """

    def __init__(self, folder_compiler: IFolderCompileProtocol | None = None) -> None:
        """Initialize adapter.

        Args:
            folder_compiler: Optional folder compiler instance. Created if None.
        """
        self._compiler = folder_compiler or FolderCompiler()

    # ─── Block 2: Public Methods ──
    def resolve_to_attachment(
        self,
        path: Path,
        max_depth: int = MAX_FOLDER_DEPTH,
    ) -> Path:
        """Resolve path to an attachment-ready file.

        Args:
            path: Path to file or folder.
            max_depth: Maximum recursion depth for folder compilation.

        Returns:
            Path to attachment file (original file or compiled markdown).

        Raises:
            FolderValidationError: If path is invalid.
            FolderCompileError: If folder compilation fails.
        """
        path = Path(path).resolve()
        log.info("Resolving path to attachment: %s", path)

        if not path.exists():
            raise FolderValidationError(f"Path does not exist: {path}")

        if self._compiler.is_folder(path):
            log.info("Path is a folder, compiling to markdown: %s", path)
            return self._compiler.compile_folder(path, max_depth=max_depth)

        if not path.is_file():
            raise FolderValidationError(f"Path is not a file or directory: {path}")

        log.info("Path is a file, using as-is: %s", path)
        return path

    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory."""
        return self._compiler.is_folder(Path(path))


__all__ = ["FolderToAttachmentAdapter"]
