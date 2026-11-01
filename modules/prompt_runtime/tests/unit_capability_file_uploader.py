"""Tests for file_uploader.py — validate_file, _close_dropdown_if_open, upload_attachment."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
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
        # Skip under root (containerised CI runs as root): root bypasses the
        # filesystem permission check this case exercises.
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
            FileUploader().validate_file(f, max_size_bytes=512)


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
            patch("modules.prompt_runtime.src.capabilities_file_uploader.time"),
            patch.object(FileUploader, "_wait_for_parse_ready"),
        ):
            result = FileUploader().upload_attachment(page, f)
            assert result is True


class TestSingleEvaluateAttachmentProbe:
    """BE-4-001: the hot path is one page.evaluate per poll, not per element."""

    def test_match_count_is_one_evaluate_and_never_touches_locators(self, tmp_path):
        f = tmp_path / "quarterly report.md"
        f.write_text("hello")
        page = MagicMock()
        page.evaluate.return_value = 2

        count = FileUploader()._attachment_match_count(page, f)

        assert count == 2
        assert page.evaluate.call_count == 1, "one evaluate computes all eight selector families"
        page.locator.assert_not_called()
        # The expected side carries the Python normalization: whitespace runs
        # collapsed to single spaces and lowercased (the JS mirrors it with
        # replace(/\\s+/g,' ').trim().toLowerCase()); stems for the stem families.
        pairs = page.evaluate.call_args.args[1]
        assert (".fileitem-file-name", "quarterly report.md") in pairs
        assert (".fileitem-file-name-text", "quarterly report") in pairs

    def test_each_card_poll_costs_exactly_one_evaluate(self, tmp_path):
        f = tmp_path / "report.md"
        f.write_text("hello")
        page = MagicMock()
        page.evaluate.side_effect = [0, 0, 2]  # two empty polls, then the card appears

        FileUploader()._wait_for_attachment_card(page, f, baseline_matches=0)

        assert page.evaluate.call_count == 3, "one evaluate per poll iteration"
        page.locator.assert_not_called()  # the locator path must not run when evaluate answers

    def test_a_probe_answer_of_the_wrong_type_fails_loudly(self, tmp_path):
        """The evaluate path is authoritative (issue 10): no silent twin scan."""
        f = tmp_path / "report.md"
        f.write_text("hello")
        page = MagicMock()  # evaluate returns a MagicMock, not an int

        with pytest.raises(TypeError, match="JS_ATTACHMENT_MATCH_COUNT"):
            FileUploader()._attachment_match_count(page, f)

    def test_parse_ready_is_one_evaluate_per_poll(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("hello")
        page = MagicMock()
        page.evaluate.return_value = {"found": True, "ready": True}

        FileUploader()._wait_for_dom_parse_ready(page, filepath)

        assert page.evaluate.call_count == 1, "one evaluate answers the whole readiness question"
        page.locator.assert_not_called()

    def test_a_parse_ready_answer_of_the_wrong_shape_fails_loudly(self, tmp_path):
        """No locator twin: an unusable probe answer is a contract violation."""
        filepath = tmp_path / "test.md"
        filepath.write_text("hello")
        page = MagicMock()
        page.evaluate.return_value = MagicMock()  # not a {found, ready} dict

        with pytest.raises(TypeError, match="JS_PARSE_READINESS"):
            FileUploader()._parse_readiness(page, filepath, ".message-input-column-file", ("parsing",))


# ─── The real JS against real DOM text (issue 1) ────────────────────────────


def _cached_chromium_executable() -> str | None:
    """Locate any installed chromium build when the default launch cannot find its own."""
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright")))
    for pattern in ("chromium-*/chrome-linux64/chrome", "chromium-*/chrome-linux/chrome"):
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_file():
                return str(candidate)
    return None


@pytest.fixture
def live_page():
    """A real headless chromium page: the only way to *execute* the shipped JS.

    The default launch is attempted first (CI runs ``playwright install
    chromium``); a developer machine whose cache carries a different build
    falls back to any installed chromium so the shipped script still runs
    against a real DOM rather than a Python reimplementation of it. When
    no usable Chromium exists at all, the real-JS tests are skipped: they
    pin script semantics, and the MagicMock type-check tests remain the
    always-on contract pins.
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception:
            executable = _cached_chromium_executable()
            if executable is None:
                pytest.skip(
                    "Chromium unavailable for live JS probe tests: default launch failed and no cached executable found"
                )
            browser = pw.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page()
        yield page
        browser.close()
    finally:
        pw.stop()


def test_the_real_js_matches_a_multi_word_filename_against_live_dom(live_page, tmp_path):
    """Regression: the element side must collapse whitespace to single spaces
    exactly like the Python expected side, so ``quarterly report.md`` matches."""
    filepath = tmp_path / "quarterly report.md"
    filepath.write_text("hello")
    live_page.set_content(
        "<div class='chat-conversation'>"
        "<div class='fileitem-file-name'>  quarterly \n  report.md  </div>"
        "<div class='fileitem-file-name'>something else.md</div>"
        "</div>"
    )

    count = FileUploader()._attachment_match_count(live_page, filepath)

    assert count == 1, (
        f"the shipped JS must count the multi-word card after collapsing whitespace runs to single spaces; got {count}"
    )


def test_the_real_js_reports_zero_for_a_different_name(live_page, tmp_path):
    filepath = tmp_path / "budget summary.md"
    filepath.write_text("hello")
    live_page.set_content(
        "<div class='chat-conversation'><div class='fileitem-file-name'>quarterly report.md</div></div>"
    )

    count = FileUploader()._attachment_match_count(live_page, filepath)

    assert count == 0, "an exact-match probe must not accept a different filename"
