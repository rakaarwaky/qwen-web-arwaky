"""Validation pure utilities: response-content + file pre-flight checks.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import CHALLENGE_KEYWORDS, RATE_LIMIT_KEYWORDS
from modules.shared.src.common.taxonomy_core_error import (
    AuthRequiredError,
    FileValidationError,
    OutputValidationError,
    RateLimitError,
)
from modules.shared.src.common.taxonomy_core_vo import ErrorReason


def validate_response_content(text: str) -> None:
    """Validate AI response text for server error pages or CAPTCHA challenges."""
    if not text or not text.strip():
        raise OutputValidationError("Response content is empty")

    text_lower = text.lower()
    for kw in RATE_LIMIT_KEYWORDS:
        if kw in text_lower and len(text) < 500:
            raise RateLimitError(ErrorReason(f"Rate limit / throttling response detected: '{kw}'"))
    for kw in CHALLENGE_KEYWORDS:
        if kw in text_lower and len(text) < 500:
            if "verify you are human" in text_lower or "attention required!" in text_lower:
                raise AuthRequiredError(f"CAPTCHA / Bot detection challenge detected: '{kw}'")
            raise OutputValidationError(f"Server error or challenge page detected in output: '{kw}'")


MAX_ATTACHMENT_SIZE_BYTES: int = 104_857_600  # 100 * 1024 * 1024 exact bytes (100 MiB)

SUPPORTED_ATTACHMENT_EXTENSIONS: tuple[str, ...] = (
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".docx",
    ".doc",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".rs",
    ".go",
)

UNSUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".bz2",
    ".xz",
    ".exe",
    ".bin",
    ".iso",
    ".dmg",
    ".so",
    ".dll",
    ".dylib",
)


def validate_file(
    filepath: object,
    max_size_mb: float | None = None,
    *,
    max_size_bytes: int = MAX_ATTACHMENT_SIZE_BYTES,
) -> int:
    """Perform pre-flight sanity, extension allowlist, exact byte ceiling, and content validation.

    Args:
        filepath: Path to the target file.
        max_size_mb: Optional maximum file size in megabytes (overrides max_size_bytes when provided).
        max_size_bytes: Maximum allowed file size in exact bytes (defaults to 104857600).

    Returns:
        File size in bytes.

    Raises:
        FileValidationError: If the file is invalid, unsupported, empty, or exceeds size limits.
    """
    if not isinstance(filepath, (str, Path)):
        raise FileValidationError(f"Invalid path: {filepath}")
    path = Path(filepath)

    if not path.exists():
        raise FileValidationError(f"File does not exist: {path}")
    if not path.is_file():
        raise FileValidationError(f"Path is not a regular file: {path}")
    if not os.access(path, os.R_OK):
        raise FileValidationError(f"File is not readable: {path}")

    ext = path.suffix.lower()
    if ext in UNSUPPORTED_EXTENSIONS or ext not in SUPPORTED_ATTACHMENT_EXTENSIONS:
        raise FileValidationError(
            f"Extension '{ext}' is not supported as an attachment by Qwen Web UI ({path.name}). "
            f"Archive and binary formats like {ext} are rejected by Qwen. "
            f"Please convert or bundle your content into a text document (.txt, .md, .py, .pdf)."
        )

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise FileValidationError(f"File is empty (0 bytes): {path}")

    max_bytes = int(max_size_mb * 1024 * 1024) if max_size_mb is not None else max_size_bytes
    if size_bytes > max_bytes:
        raise FileValidationError(f"File size ({size_bytes} bytes) exceeds maximum limit of {max_bytes} bytes: {path}")

    _validate_type_content_match(path, ext)

    return size_bytes


def _validate_type_content_match(path: Path, ext: str) -> None:
    """Validate that the file header matches its claimed extension (rejects mismatches)."""
    try:
        with path.open("rb") as f:
            header = f.read(512)
    except Exception as exc:
        raise FileValidationError(f"File is not readable: {path}") from exc

    if ext == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise FileValidationError(
                f"Content does not match extension '{ext}' (expected PDF magic header %PDF-): {path}"
            )
    elif ext in {".txt", ".md", ".markdown", ".py", ".json", ".yaml", ".yml", ".xml", ".csv", ".tsv", ".html", ".htm"}:
        if b"\x00" in header:
            raise FileValidationError(
                f"Content does not match extension '{ext}' (binary null byte detected in text format): {path}"
            )
    elif ext == ".docx" and not header.startswith(b"PK\x03\x04"):
        raise FileValidationError(f"Content does not match extension '{ext}' (expected ZIP/OOXML magic header): {path}")
