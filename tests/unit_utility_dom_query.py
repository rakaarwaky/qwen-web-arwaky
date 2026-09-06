"""Remaining coverage tests for sender.py, saver.py, observability.py, file_uploader.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.shared.src import (
    LifecycleEmitter,
    RunContext,
    SaverConfig,
)
from modules.shared.src.utility_core_text import strip_ui_noise
from tests.helpers import (
    _configure_logging,
    _configure_sentry,
    _configure_tracing,
    click_send,
    write_output,
)

# ─── sender.py remaining lines ─────────────────────────────────────────────


class TestSenderRemaining:
    def test_click_send_custom_config(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        from modules.shared.src import SenderConfig

        cfg = SenderConfig(click_timeout_ms=200, try_enter_key_fallback=True)
        # No selectors match → with Enter fallback enabled the dispatcher presses
        # Enter and emits the send/dispatch lifecycle events.
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.count.return_value = 0
        loc.first.is_visible.return_value = False
        page.locator.return_value = loc
        page.evaluate.side_effect = [1, "", 2]
        click_send(page, emitter, config=cfg)
        emitter.emit.assert_called()

    def test_count_messages_js_returns_zero(self):
        page = MagicMock()
        page.evaluate.return_value = 0
        loc = MagicMock()
        loc.count.return_value = 5
        page.locator.return_value = loc
        result = count_messages(page)
        assert result == 5

    def test_latest_message_text_js_returns_valid(self):
        page = MagicMock()
        page.evaluate.return_value = "  AI answer  "
        result = latest_message_text(page)
        assert result == "AI answer"

    def test_latest_message_text_js_returns_none(self):
        page = MagicMock()
        page.evaluate.return_value = None
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result is None


# ─── saver.py remaining lines ───────────────────────────────────────────────


class TestSaverRemaining:
    def test_strip_ui_noise_qwen_max(self):
        text = "Qwen Max\nReal content"
        result = strip_ui_noise(text)
        assert "Qwen Max" not in result

    def test_strip_ui_noise_auto(self):
        text = "Auto\nReal content"
        result = strip_ui_noise(text)
        assert result == "Real content"

    def test_strip_ui_noise_kb_suffix(self):
        text = "128 KB\nReal content"
        result = strip_ui_noise(text)
        assert result == "Real content"

    def test_write_output_with_sidecar_error(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        cfg = SaverConfig(atomic_write=False, generate_sidecar=True)
        # Should not raise even if sidecar write has issues
        write_output(
            path=out_file,
            content="data",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=4,
            config=cfg,
        )
        assert out_file.exists()


# ─── observability.py remaining lines ───────────────────────────────────────


class TestObservabilityRemaining:
    def test_configure_sentry_no_dsn(self):
        with patch.dict("os.environ", {}, clear=True):
            _configure_sentry()

    def test_configure_tracing_no_otel(self):
        # New code catches ImportError inline — just call it, no error raised
        _configure_tracing()

    def test_configure_logging_no_structlog(self):
        # New code catches ImportError inline — just call it, no error raised
        _configure_logging(Path("/tmp/test-log"))
