"""Workspace boundary path validation (AES Utility layer).

Stateless helpers that enforce confinement of user-provided paths to a
workspace root. Used by both CLI and MCP surfaces for consistent security.

The workspace root is determined by:
1. Explicit ``QWEN_WORKSPACE_ROOT`` environment variable (highest priority)
2. Current working directory (fallback)

All paths are resolved (expanduser + resolve) before the boundary check.

The four public validators share one implementation — ``_validate_path`` —
so the resolve / existence / type / workspace-boundary rules and the
error-dict shape can never drift between them. Each public function only
supplies the predicate that distinguishes its rule and the messages that
name the failure.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = [
    "validate_prompt_path",
    "validate_attachment_path",
    "validate_output_path",
    "validate_swarm_input_path",
    "validate_swarm_id",
    "_get_workspace_root",
    "_sanitize_path_for_error",
]


def _get_workspace_root() -> Path:
    """Return the workspace root used for path confinement.

    Precedence:
    - ``QWEN_WORKSPACE_ROOT`` environment variable (if set and valid)
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

    Uses ``relative_to()`` which raises ``ValueError`` if path is not a
    subpath. This also neutralizes symlinks since ``Path.resolve()``
    unfolds them.
    """
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


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


def _outside_workspace_error(path: Path, field: str) -> dict[str, Any]:
    """Build the shared ``PATH_OUTSIDE_WORKSPACE`` error dict."""
    return {
        "code": "PATH_OUTSIDE_WORKSPACE",
        "message": f"Path is outside the workspace root: {_sanitize_path_for_error(path)}",
        "hint": f"Place files under {_get_workspace_root()} or set QWEN_WORKSPACE_ROOT.",
        "field": field,
    }


def _validate_path(
    raw: str,
    *,
    field: str,
    exists_message: str,
    exists_hint: str,
    type_message: str,
    type_hint: str,
    type_check: Callable[[Path], bool],
    target_for_boundary: Callable[[Path], Path],
) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve *raw*, then run the shared existence / type / boundary checks.

    The four public validators differ only in their predicate, their
    error wording, and which path component is boundary-checked, so they
    delegate here instead of each re-implementing the same three checks.
    """
    try:
        resolved = Path(raw).expanduser().resolve()
    except (OSError, ValueError) as exc:
        return None, {
            "code": "INVALID_PATH",
            "message": f"Invalid {field} path: {raw}",
            "hint": f"Path resolution failed: {exc}",
            "field": field,
        }

    if not resolved.exists():
        return None, {
            "code": "FILE_NOT_FOUND",
            "message": exists_message,
            "hint": exists_hint,
            "field": field,
        }

    if not type_check(resolved):
        return None, {
            "code": "INVALID_PATH",
            "message": type_message,
            "hint": type_hint,
            "field": field,
        }

    boundary_target = target_for_boundary(resolved)
    root = _get_workspace_root()
    if not _is_within_workspace(boundary_target, root):
        return None, _outside_workspace_error(boundary_target, field)

    return resolved, None


def validate_prompt_path(raw: str, field: str = "prompt_file") -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a prompt file path and verify it stays within the workspace.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    return _validate_path(
        raw,
        field=field,
        exists_message=f"Prompt file not found: {_sanitize_path_for_error(Path(raw).expanduser().resolve())}",
        exists_hint="Check the prompt path or use init_workspace.",
        type_message="Prompt path is not a regular file.",
        type_hint="Prompt files must be regular files.",
        type_check=lambda p: p.is_file(),
        target_for_boundary=lambda p: p,
    )


def validate_attachment_path(raw: str, field: str = "attachment_file") -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve an attachment path (file or directory) and verify workspace confinement.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    return _validate_path(
        raw,
        field=field,
        exists_message="Attachment file or folder not found.",
        exists_hint="Check attachment_file path. Can be a file or directory.",
        type_message="Attachment path is not a regular file or directory.",
        type_hint="FIFOs, sockets, and device nodes are not supported.",
        type_check=lambda p: p.is_file() or p.is_dir(),
        target_for_boundary=lambda p: p,
    )


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
        return None, _outside_workspace_error(parent, field)

    return o_path, None


def validate_swarm_input_path(
    raw: str,
) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve a swarm input path (file or directory) and verify workspace confinement.

    Swarm input can be a file or directory containing role templates.

    Returns:
        (path, None) on success
        (None, error_dict) on failure
    """
    return _validate_path(
        raw,
        field="input",
        exists_message="Swarm input not found.",
        exists_hint="Check the input path.",
        type_message="Swarm input is not a regular file or directory.",
        type_hint="Input must be a file or directory.",
        type_check=lambda p: p.is_file() or p.is_dir(),
        target_for_boundary=lambda p: p,
    )


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
