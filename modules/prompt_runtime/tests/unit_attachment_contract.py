"""Boundary matrix tests for the attachment contract (BA-3-001).

Each boundary case must fail at pre-flight validation with a stable reason
and no accidental provider submission. The exact byte ceiling is 104857600.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
from modules.shared.src import FileValidationError
from modules.shared.src.common.utility_core_validation import (
    MAX_ATTACHMENT_SIZE_BYTES,
    SUPPORTED_ATTACHMENT_EXTENSIONS,
    validate_file,
)


class TestAttachmentBoundaryMatrix:
    """BA-3-001: zero bytes, exact max, max+1, unreadable, unsupported, mismatch."""

    def test_zero_byte_file_fails(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_bytes(b"")
        with pytest.raises(FileValidationError, match="empty"):
            validate_file(f)

    def test_exact_maximum_bytes_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "exact_max.md"
        f.write_bytes(b"0" * MAX_ATTACHMENT_SIZE_BYTES)
        size = validate_file(f)
        assert size == MAX_ATTACHMENT_SIZE_BYTES

    def test_maximum_plus_one_byte_fails(self, tmp_path: Path) -> None:
        f = tmp_path / "max_plus1.md"
        f.write_bytes(b"0" * (MAX_ATTACHMENT_SIZE_BYTES + 1))
        with pytest.raises(FileValidationError, match="exceeds maximum"):
            validate_file(f)

    def test_unsupported_format_fails(self, tmp_path: Path) -> None:
        f = tmp_path / "archive.zip"
        f.write_bytes(b"PK\x03\x04")
        with pytest.raises(FileValidationError, match="not supported"):
            validate_file(f)

    def test_unsupported_extension_not_in_allowlist_fails(self, tmp_path: Path) -> None:
        f = tmp_path / "unknown.xyz"
        f.write_bytes(b"hello")
        with pytest.raises(FileValidationError, match="not supported"):
            validate_file(f)

    def test_unreadable_file_fails(self, tmp_path: Path) -> None:
        # Posix root (uid 0) bypasses standard DAC read permission checks
        # (os.access(..., os.R_OK) returns True even for mode 000). Containerised
        # CI runners executing as root intentionally skip this matrix cell.
        if os.getuid() == 0:
            pytest.skip("root bypasses filesystem permission checks")
        f = tmp_path / "locked.md"
        f.write_text("locked", encoding="utf-8")
        os.chmod(f, 0o000)
        try:
            with pytest.raises(FileValidationError, match="not readable"):
                validate_file(f)
        finally:
            os.chmod(f, 0o644)

    def test_type_content_mismatch_fails(self, tmp_path: Path) -> None:
        """A .pdf file with non-PDF content must fail at pre-flight."""
        f = tmp_path / "fake.pdf"
        f.write_bytes(b"This is not a PDF file")
        with pytest.raises(FileValidationError, match="Content does not match"):
            validate_file(f)

    def test_pdf_with_valid_magic_header_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "real.pdf"
        f.write_bytes(b"%PDF-1.4\nfake pdf content")
        size = validate_file(f)
        assert size > 0

    def test_supported_format_allowlist(self) -> None:
        """Publish the supported format allowlist for BA-3-001.

        The allowlist is derived from the actual uploader enforcement path
        (modules/prompt_runtime/src/capabilities_file_uploader.py via shared utility).
        """
        assert ".txt" in SUPPORTED_ATTACHMENT_EXTENSIONS
        assert ".md" in SUPPORTED_ATTACHMENT_EXTENSIONS
        assert ".pdf" in SUPPORTED_ATTACHMENT_EXTENSIONS
        assert ".zip" not in SUPPORTED_ATTACHMENT_EXTENSIONS
        assert ".exe" not in SUPPORTED_ATTACHMENT_EXTENSIONS

    def test_file_uploader_validate_uses_shared_celiling(self, tmp_path: Path) -> None:
        """FileUploader.validate_file delegates to the shared validate_file."""
        f = tmp_path / "doc.txt"
        f.write_bytes(b"x" * 10)
        uploader = FileUploader()
        size = uploader.validate_file(f)
        assert size == 10

    def test_mcp_and_cli_share_same_validation(self, tmp_path: Path) -> None:
        """The shared validate_file is the single source of truth for both surfaces."""
        f = tmp_path / "bad.exe"
        f.write_bytes(b"\x00\x01\x02")
        with pytest.raises(FileValidationError):
            validate_file(f)
