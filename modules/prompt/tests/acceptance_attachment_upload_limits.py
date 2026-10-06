"""Acceptance tests for the attachment-prompt requirement.

The requirement in `modules/prompt/FRD.md` FR-PROMPT-003 is that an
attachment passes the size and type limits the upload seam enforces before
the send, and that an over-ceiling upload is rejected with the limit named.
These drive the real uploader's pre-send validation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter
from modules.prompt.src.capabilities_file_uploader import FileUploader


def _attachment(tmp_path: Path, size_bytes: int) -> Path:
    """Return an attachment of *size_bytes* at a real path."""
    attachment = tmp_path / "report.md"
    attachment.write_bytes(b"x" * size_bytes)
    return attachment


def test_acceptance_an_attachment_within_the_ceiling_reports_its_size(tmp_path: Path) -> None:
    attachment = _attachment(tmp_path, 1024)

    size = FileUploader().validate_file(attachment, max_size_mb=1.0)

    assert size == 1024


def test_acceptance_an_attachment_over_the_ceiling_is_rejected(tmp_path: Path) -> None:
    oversized = _attachment(tmp_path, 2 * 1024 * 1024)

    with pytest.raises(Exception) as excinfo:
        FileUploader().validate_file(oversized, max_size_mb=1.0)

    assert "1.0" in str(excinfo.value), f"the rejection must name the limit, got: {excinfo.value}"


def test_acceptance_a_missing_attachment_is_rejected_at_validation(tmp_path: Path) -> None:
    """The pipeline must not spend browser time discovering a file that
    was never there."""
    with pytest.raises(Exception):
        FileUploader().validate_file(tmp_path / "absent.md", max_size_mb=1.0)


def test_acceptance_a_missing_prompt_file_is_reported_before_the_send(tmp_path: Path) -> None:
    """The adapter checks the prompt path before it opens a browser, so a
    file that was never there costs no browser time.

    Note: the adapter returns the failure as an error string rather than
    raising, so this asserts the response text rather than an exception.
    """
    adapter = AttachmentPromptAdapter(*(MagicMock() for _ in range(10)))

    result = adapter.process_prompt_with_attachment(
        prompt_file=tmp_path / "absent-prompt.md",
        attachment_file=tmp_path / "report.md",
        output_file=tmp_path / "out.md",
        headless=True,
    )

    assert "not found" in str(result).lower(), f"the failure must name the missing file, got: {result}"
