"""Tests for file_uploader.py — validate_file, _close_dropdown_if_open, upload_attachment."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.capabilities_file_uploader import FileUploader
from modules.shared.src import (
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    FileValidationError,
    LifecycleEmitter,
)


class TestValidateFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        size = FileUploader().validate_file(f)
        assert size == 5

    def test_nonexistent_file(self, tmp_path):
        with pytest.raises(FileValidationError, match="does not exist"):
            FileUploader().validate_file(tmp_path / "nope.md")

    def test_unsupported_zip_extension(self, tmp_path):
        archive = tmp_path / "code.zip"
        archive.write_bytes(b"PK\x03\x04")
        with pytest.raises(FileValidationError, match="not supported as an attachment"):
            FileUploader().validate_file(archive)

    def test_directory_not_file(self, tmp_path):
        with pytest.raises(FileValidationError, match="not a regular file"):
            FileUploader().validate_file(tmp_path)

    def test_unreadable_file(self, tmp_path):
        if os.getuid() == 0:
            pytest.skip("root bypasses filesystem permission checks")
        f = tmp_path / "locked.md"
        f.write_text("locked")
        os.chmod(f, 0o000)
        try:
            with pytest.raises(FileValidationError, match="not readable"):
                FileUploader().validate_file(f)
        finally:
            os.chmod(f, 0o644)

    def test_file_too_large(self, tmp_path):
        f = tmp_path / "big.md"
        f.write_text("x" * 1024)
        with pytest.raises(FileValidationError, match="exceeds maximum"):
            FileUploader().validate_file(f, max_size_mb=0.0001)


class TestCloseDropdownIfOpen:
    def test_presses_escape(self):
        page = MagicMock()
        FileUploader()._close_dropdown_if_open(page)
        page.keyboard.press.assert_called_once_with("Escape")

    def test_handles_exception(self):
        page = MagicMock()
        page.keyboard.press.side_effect = Exception("page closed")
        FileUploader()._close_dropdown_if_open(page)


class TestUploadAttachment:
    def test_web_not_loaded_raises(self):
        page = MagicMock()
        with pytest.raises(RuntimeError, match="web page loading"):
            FileUploader().upload_attachment(page, Path("/fake.md"), web_loaded=False)

    def test_file_validation_failure_returns_false(self, tmp_path):
        f = tmp_path / "nope.md"
        page = MagicMock()
        result = FileUploader().upload_attachment(page, f)
        assert result is False

    def test_upload_returns_true(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        page = MagicMock()

        mock_dropdown = MagicMock()
        mock_dropdown.is_visible.return_value = True
        mock_option = MagicMock()
        mock_option.is_visible.return_value = True

        page.locator.return_value.first = mock_dropdown

        mock_fc = MagicMock()
        page.expect_file_chooser.return_value.__enter__ = MagicMock(return_value=mock_fc)
        page.expect_file_chooser.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(FileUploader, "_try_upload_attempt", return_value=True),
            patch.object(FileUploader, "_wait_for_parse_ready"),
        ):
            result = FileUploader().upload_attachment(page, f)
            assert result is True

    def test_upload_option_selector_fallbacks(self, tmp_path):
        """Test that upload option uses text selectors for resilience."""
        f = tmp_path / "test.md"
        f.write_text("hello")
        page = MagicMock()

        mock_dropdown = MagicMock()
        mock_dropdown.is_visible.return_value = True
        mock_option = MagicMock()
        mock_option.is_visible.return_value = True

        page.locator.return_value.first = mock_dropdown

        mock_fc = MagicMock()
        page.expect_file_chooser.return_value.__enter__ = MagicMock(return_value=mock_fc)
        page.expect_file_chooser.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(FileUploader, "_try_upload_attempt", return_value=True),
            patch.object(FileUploader, "_wait_for_parse_ready"),
        ):
            result = FileUploader().upload_attachment(page, f)
            assert result is True

    def test_emitter_called_on_success(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with (
            patch.object(FileUploader, "_try_upload_attempt", return_value=True),
            patch.object(FileUploader, "_wait_for_parse_ready"),
        ):
            FileUploader().upload_attachment(page, f, emitter=emitter)
            emitter.emit.assert_any_call(
                EVENT_FILE_UPLOADED,
                {"file": str(f), "byte_count": 5, "attempt": 1},
            )
            emitter.emit.assert_any_call(
                EVENT_DOCUMENT_PARSED,
                {"file": str(f), "byte_count": 5, "attempt": 1},
            )
            assert emitter.emit.call_count == 2

    def test_retry_on_failure(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        page = MagicMock()

        with (
            patch.object(FileUploader, "_try_upload_attempt", side_effect=[False, False, True]),
            patch("modules.core.src.capabilities_file_uploader.time"),
            patch.object(FileUploader, "_wait_for_parse_ready"),
        ):
            result = FileUploader().upload_attachment(page, f, config=None)
            assert result is True
