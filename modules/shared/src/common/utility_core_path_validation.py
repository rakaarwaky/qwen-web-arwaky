"""Workspace boundary path validation (AES Utility layer).

Stateless helpers that enforce confinement of user-provided paths to a
workspace root. Used by both CLI and MCP surfaces for consistent security.

The workspace root is determined by:
1. Explicit `QWEN_WORKSPACE_ROOT` environment variable (highest priority)
2. Current working directory (fallback)

All paths are resolved (expanduser + resolve) before the boundary check.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _get_workspace_root() -> Path:
    """Return the workspace root used for path confinement.

    Precedence:
    - QWEN_WORKSPACE_ROOT environment variable (if set and valid)
    - Current working directory
    """
    root = os.environ.get("QWEN_WORKSPACE_ROOT")
    if root:
        try:
            return Path(root).expanduser().resolve()
        except (OSError, ValueError):
            pass
    return Path.cwd().resolve()


def _is_within_workspace(path: Path, root: Path) -> bool:
    """Check if a resolved path is within the workspace root.

    Uses relative_to() which raises ValueError if path is not a subpath.
    This also neutralizes symlinks since Path.resolve() unfolds them.
    """
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_prompt_path(raw: str, field: str = "prompt_file") -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a prompt file path and verify it stays within the workspace.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    try:
        p_path = Path(raw).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return None, {
            "code": "INVALID_PATH",
            "message": f"Invalid prompt path: {raw}",
            "hint": f"Path resolution failed: {exc}",
            "field": field,
        }

    if not p_path.exists():
        return None, {
            "code": "FILE_NOT_FOUND",
            "message": f"Prompt file not found: {_sanitize_path_for_error(p_path)}",
            "hint": "Check the prompt path or use init_workspace.",
            "field": field,
        }

    if not p_path.is_file():
        return None, {
            "code": "INVALID_PATH",
            "message": f"Prompt path is not a regular file: {_sanitize_path_for_error(p_path)}",
            "hint": "Prompt files must be regular files.",
            "field": field,
        }

    root = _get_workspace_root()
    if not _is_within_workspace(p_path, root):
        return None, {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": f"Prompt path is outside the workspace root: {_sanitize_path_for_error(p_path)}",
            "hint": f"Place files under {root} or set QWEN_WORKSPACE_ROOT.",
            "field": field,
        }

    return p_path, None


def validate_attachment_path(raw: str, field: str = "attachment_file") -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve an attachment path (file or directory) and verify workspace confinement.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    try:
        a_path = Path(raw).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return None, {
            "code": "INVALID_PATH",
            "message": f"Invalid attachment path: {raw}",
            "hint": f"Path resolution failed: {exc}",
            "field": field,
        }

    if not a_path.exists():
        return None, {
            "code": "FILE_NOT_FOUND",
            "message": f"Attachment file or folder not found: {_sanitize_path_for_error(a_path)}",
            "hint": "Check attachment_file path. Can be a file or directory.",
            "field": field,
        }

    if not (a_path.is_file() or a_path.is_dir()):
        return None, {
            "code": "INVALID_PATH",
            "message": f"Attachment path is not a regular file or directory: {_sanitize_path_for_error(a_path)}",
            "hint": "FIFOs, sockets, and device nodes are not supported.",
            "field": field,
        }

    root = _get_workspace_root()
    if not _is_within_workspace(a_path, root):
        return None, {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": f"Attachment path is outside the workspace root: {_sanitize_path_for_error(a_path)}",
            "hint": f"Place files under {root} or set QWEN_WORKSPACE_ROOT.",
            "field": field,
        }

    return a_path, None


def validate_output_path(raw: str, field: str = "output_file") -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve an output path and verify workspace confinement.

    Unlike prompt/attachment, the output file doesn't need to exist yet,
    but its parent directory must exist and be within the workspace.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    try:
        o_path = Path(raw).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return None, {
            "code": "INVALID_PATH",
            "message": f"Invalid output path: {raw}",
            "hint": f"Path resolution failed: {exc}",
            "field": field,
        }

    # Parent must exist and be within workspace
    parent = o_path.parent
    if not parent.exists():
        return None, {
            "code": "FILE_NOT_FOUND",
            "message": f"Output directory does not exist: {_sanitize_path_for_error(parent)}",
            "hint": "Create the parent directory first.",
            "field": field,
        }

    if not parent.is_dir():
        return None, {
            "code": "INVALID_PATH",
            "message": f"Output parent is not a directory: {_sanitize_path_for_error(parent)}",
            "hint": "Output must be written to a directory.",
            "field": field,
        }

    root = _get_workspace_root()
    if not _is_within_workspace(parent, root):
        return None, {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": f"Output path is outside the workspace root: {_sanitize_path_for_error(o_path)}",
            "hint": f"Place output under {root} or set QWEN_WORKSPACE_ROOT.",
            "field": field,
        }

    return o_path, None


def _sanitize_path_for_error(path: Path) -> str:
    """Sanitize a path for display in error messages.

    Shows only the basename or a relative path from the workspace root
    to avoid leaking internal directory structure and usernames.
    """
    root = _get_workspace_root()
    try:
        rel = path.relative_to(root)
        return str(rel)
    except ValueError:
        # Path is outside workspace — show only basename
        return path.name


def validate_swarm_input_path(raw: str) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a swarm input path (file or directory) and verify workspace confinement.

    Swarm input can be a file or directory containing role templates.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    try:
        p_path = Path(raw).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return None, {
            "code": "INVALID_PATH",
            "message": f"Invalid swarm input path: {raw}",
            "hint": f"Path resolution failed: {exc}",
            "field": "input",
        }

    if not p_path.exists():
        return None, {
            "code": "FILE_NOT_FOUND",
            "message": f"Swarm input not found: {_sanitize_path_for_error(p_path)}",
            "hint": "Check the input path.",
            "field": "input",
        }

    if not (p_path.is_file() or p_path.is_dir()):
        return None, {
            "code": "INVALID_PATH",
            "message": f"Swarm input is not a regular file or directory: {_sanitize_path_for_error(p_path)}",
            "hint": "Input must be a file or directory.",
            "field": "input",
        }

    root = _get_workspace_root()
    if not _is_within_workspace(p_path, root):
        return None, {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": f"Swarm input is outside the workspace root: {_sanitize_path_for_error(p_path)}",
            "hint": f"Place input under {root} or set QWEN_WORKSPACE_ROOT.",
            "field": "input",
        }

    return p_path, None


def validate_swarm_id(swarm_id: str) -> dict[str, Any] | None:
    """Validate a swarm ID format.

    Returns None if valid, error_dict if invalid.
    """
    if not swarm_id or not swarm_id.strip():
        return {
            "code": "VALIDATION_ERROR",
            "message": "swarm_id must not be empty.",
            "hint": "Provide a valid swarm ID.",
            "field": "swarm_id",
        }
    if len(swarm_id) > 128:
        return {
            "code": "VALIDATION_ERROR",
            "message": f"swarm_id too long: {len(swarm_id)} characters (max 128).",
            "hint": "Use a shorter identifier.",
            "field": "swarm_id",
        }
    if any(c in swarm_id for c in "/\\\0"):
        return {
            "code": "VALIDATION_ERROR",
            "message": "swarm_id contains invalid characters (/ \\ \\0).",
            "hint": "Use alphanumeric characters, dashes, underscores.",
            "field": "swarm_id",
        }
    return None


__all__ = [
    "validate_prompt_path",
    "validate_attachment_path",
    "validate_output_path",
    "validate_swarm_input_path",
    "validate_swarm_id",
    "_get_workspace_root",
    "_sanitize_path_for_error",
]
