"""CLI surface: folder command — compile a folder to a single Markdown file.

Smart surface: maps parsed args to the folder-compiler verb (compile_folder)
and formats the result as a human-readable confirmation line. No JSON output,
no Qwen round-trip.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Protocol

from modules.shared.src.common.taxonomy_core_error import (
    FolderCompileError,
    FolderEmptyError,
    FolderValidationError,
)

_ERROR_PREFIX = "[ERROR]"


class _FolderCompiler(Protocol):
    """Structural type for the folder-compiler capability consumed here.

    The concrete capability lives in the Capabilities layer; declaring the
    call-shape protocol locally keeps the surface free of forbidden
    Capabilities/contract imports while still type-checking calls to
    ``compile_folder``. The dispatch passes the concrete compiler instance
    (``container.folder_compiler``), which structurally satisfies this
    protocol without the surface importing the capability class.
    """

    def compile_folder(
        self,
        folder_path: Path,
        output_path: Path | None = None,
        max_depth: int = 5,
        import_depth: int = 1,
        include_imports: bool = True,
        boundary_root: Path | None = None,
    ) -> Path: ...


def handle_folder_command(args: argparse.Namespace, compiler: _FolderCompiler) -> int:
    """Handle the ``folder`` subcommand: compile a folder to Markdown.

    Usage: ``qwa folder <path>``.

    ``args.folder_path`` is the positional set by the parser.
    """
    folder_path_raw = getattr(args, "folder_path", None)
    if not folder_path_raw:
        print("Missing folder path. Usage: qwen-web-arwaky folder <path>", file=sys.stderr)
        return 1

    try:
        output_path = compiler.compile_folder(Path(folder_path_raw))
    except (
        FolderValidationError,
        FolderEmptyError,
        FolderCompileError,
        OSError,
    ) as exc:
        print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
        return 1

    print(f"Compiled {folder_path_raw} -> {output_path}")
    return 0


__all__ = ["handle_folder_command"]
