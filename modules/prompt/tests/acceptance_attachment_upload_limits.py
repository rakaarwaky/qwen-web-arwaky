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
from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader


def _attachment(tmp_path: Path, size_bytes: int) -> Path:
    """Return an attachment of *size_bytes* at a real path."""
    attachment = tmp_path / "report.md"
    attachment.write_bytes(b"x" * size_bytes)
    return attachment


def test_acceptance_an_attachment_within_the_ceiling_reports_its_size(tmp_path: Path) -> None:
    attachment = _attachment(tmp_path, 1024)

    size = FileUploader().validate_file(attachment, max_size_bytes=1024 * 1024)

    assert size == 1024


def test_acceptance_an_attachment_over_the_ceiling_is_rejected(tmp_path: Path) -> None:
    oversized = _attachment(tmp_path, 2 * 1024 * 1024)

    with pytest.raises(Exception) as excinfo:
        FileUploader().validate_file(oversized, max_size_bytes=1024 * 1024)

    assert "exceeds maximum limit of 1048576 bytes" in str(excinfo.value), (
        f"the rejection must name the limit in bytes, got: {excinfo.value}"
    )


def test_acceptance_a_missing_attachment_is_rejected_at_validation(tmp_path: Path) -> None:
    """The pipeline must not spend browser time discovering a file that
    was never there."""
    with pytest.raises(Exception):
        FileUploader().validate_file(tmp_path / "absent.md", max_size_bytes=1024 * 1024)


def test_acceptance_a_missing_prompt_file_is_reported_before_the_send(tmp_path: Path) -> None:
    """The adapter checks the prompt path before it opens a browser, so a
    file that was never there costs no browser time.

    Note: the adapter returns the failure as an error string rather than
    raising, so this asserts the response text rather than an exception.
    """
    adapter = AttachmentPromptAdapter(
        browser_lifecycle=MagicMock(),
        browser_navigation=MagicMock(),
        browser_diagnostics=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(),
        flow=MagicMock(),
        folder_adapter=MagicMock(),
        cancel=MagicMock(),
    )

    result = adapter.process_prompt_with_attachment(
        prompt_file=tmp_path / "absent-prompt.md",
        attachment_file=tmp_path / "report.md",
        output_file=tmp_path / "out.md",
        headless=True,
    )

    assert "not found" in str(result.response_text).lower(), f"the failure must name the missing file, got: {result}"


def test_acceptance_invalid_attachment_surfaces_stable_reason_without_browser_launch(
    tmp_path: Path,
) -> None:
    """BA-3-001: A bad attachment (e.g. fake .pdf) fails pre-flight validation
    at the adapter level with an ERROR [FileValidationError] response containing
    the stable reason, and the browser seam is never entered.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Review this document", encoding="utf-8")

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"This is not a PDF file")

    uploader = FileUploader()
    browser_mock = MagicMock()
    folder_adapter = MagicMock()
    folder_adapter.resolve_to_attachment.side_effect = lambda p: p

    adapter = AttachmentPromptAdapter(
        browser_lifecycle=browser_mock,
        browser_navigation=MagicMock(),
        browser_diagnostics=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=uploader,
        saver=MagicMock(),
        observability=MagicMock(),
        flow=MagicMock(),
        folder_adapter=folder_adapter,
        cancel=MagicMock(),
    )

    result = adapter.process_prompt_with_attachment(
        prompt_file=prompt,
        attachment_file=fake_pdf,
        output_file=tmp_path / "out.md",
        headless=True,
    )

    result_str = str(result.response_text)
    assert result_str.startswith("ERROR [FileValidationError]:"), (
        f"must start with ERROR [FileValidationError], got: {result_str}"
    )
    assert "Content does not match extension '.pdf'" in result_str, (
        f"must contain stable reason string, got: {result_str}"
    )
    browser_mock.browser_session.assert_not_called()
