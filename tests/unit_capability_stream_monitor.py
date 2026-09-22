"""Regression tests for streamer module — validate_response_content, is_generation_complete, wait_for_response edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.capabilities_stream_monitor import (
    StreamMonitor,
    validate_response_content,
)
from modules.shared.src import (
    CHALLENGE_KEYWORDS,
    EVENT_GENERATION_FINISHED,
    EVENT_STREAMING_GENERATION,
    AuthRequiredError,
    LifecycleEmitter,
    OutputValidationError,
)
from modules.shared.src.taxonomy_core_constant import JS_GET_RESPONSE_TEXT
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError, StuckDetectedError

# ─── validate_response_content ──────────────────────────────────────────────


class TestValidateResponseContent:
    def test_valid_long_response(self):
        text = "Here is a detailed explanation of how to use Playwright for browser automation. " * 3
        validate_response_content(text)  # no exception

    def test_valid_short_response(self):
        validate_response_content("OK")

    def test_empty_string_raises(self):
        with pytest.raises(OutputValidationError, match="empty"):
            validate_response_content("")

    def test_whitespace_only_raises(self):
        with pytest.raises(OutputValidationError, match="empty"):
            validate_response_content("   \n\t  ")

    def test_captcha_challenge(self):
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content("Please verify you are human to continue.")

    def test_attention_required(self):
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content("Attention Required! Cloudflare check.")

    def test_502_bad_gateway(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("502 Bad Gateway")

    def test_504_gateway_timeout(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("504 Gateway Time-out")

    def test_service_unavailable(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Service Unavailable")

    def test_access_denied(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Access Denied")

    def test_upload_still_processing(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Oops! There are files still uploading")

    def test_please_wait_for_upload(self):
        with pytest.raises(OutputValidationError, match="Server error"):
            validate_response_content("Please wait for the upload to complete")

    def test_challenge_keywords_all_covered(self):
        for kw in CHALLENGE_KEYWORDS:
            text = f"Error: {kw}"
            with pytest.raises((OutputValidationError, AuthRequiredError)):
                validate_response_content(text)

    def test_long_text_with_challenge_keyword_passes(self):
        long_text = ("502 bad gateway " + "word " * 200).strip()
        validate_response_content(long_text)

    def test_challenge_keyword_in_long_text_still_raises(self):
        text = "Please verify you are human. " + "word " * 50
        with pytest.raises(AuthRequiredError, match="CAPTCHA"):
            validate_response_content(text)


# ─── is_generation_complete ─────────────────────────────────────────────────


class TestIsGenerationComplete:
    def test_complete_when_send_enabled_no_stop(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 0
        page.evaluate.return_value = False  # no active thinking indicator

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert StreamMonitor().is_generation_complete(page) is True

    def test_incomplete_when_stop_visible(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 1
        stop_btn.first.is_visible.return_value = True

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert StreamMonitor().is_generation_complete(page) is False

    def test_incomplete_when_send_disabled(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 1
        send_disabled.first.is_visible.return_value = True
        typing = MagicMock()
        typing.count.return_value = 0

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            if "thinking" in sel or "typing" in sel:
                return typing
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert StreamMonitor().is_generation_complete(page) is False

    def test_incomplete_when_typing_visible(self):
        page = MagicMock()
        stop_btn = MagicMock()
        stop_btn.count.return_value = 0
        send_disabled = MagicMock()
        send_disabled.count.return_value = 0
        page.evaluate.return_value = True  # active thinking indicator detected

        def locator_factory(sel):
            if "Stop" in sel:
                return stop_btn
            if "disabled" in sel:
                return send_disabled
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        assert StreamMonitor().is_generation_complete(page) is False

    def test_exception_returns_false(self):
        page = MagicMock()
        page.locator.side_effect = Exception("browser crash")
        assert StreamMonitor().is_generation_complete(page) is False


# ─── wait_for_response edge cases ───────────────────────────────────────────


class TestWaitForResponseEdgeCases:
    def test_dispatch_not_acknowledged_raises(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            StreamMonitor().wait_for_response(
                page, timeout_sec=10, msg_count_before=0, emitter=emitter, dispatch_acknowledged=False
            )

    def test_safety_circuit_breaker_raises_after_configured_budget(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with (
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 14_400]
            mock_time.sleep = MagicMock()

            with pytest.raises(ResponseDetectionTimeoutError, match="circuit breaker"):
                StreamMonitor(safety_timeout_sec=14_400).wait_for_response(
                    page,
                    timeout_sec=120,
                    msg_count_before=1,
                    emitter=emitter,
                    polling_interval_sec=0,
                )

    def test_playwright_timeout_is_recovered_without_failing(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        response = "A response recovered after a transient browser timeout."

        with (
            patch(
                "modules.core.src.capabilities_stream_monitor._dom_latest",
                side_effect=[None, TimeoutError("temporary"), response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 1, 2, 3, 4, 5]
            mock_time.sleep = MagicMock()

            # Budget (120s) comfortably covers the mocked 5s sequence; the
            # test targets transient Playwright TimeoutError recovery, not
            # the hard cutoff (issue #372).
            result = StreamMonitor(safety_timeout_sec=100).wait_for_response(
                page,
                timeout_sec=120,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=1,
            )

        assert result == response

    def test_wait_continues_until_terminal_event_within_timeout_budget(self):
        """Inside the timeout budget the loop must wait for the terminal
        event (not return early); the hard cutoff only fires once the budget
        is exhausted (issue #372; covered in TestHardResponseTimeout)."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        response = "A delayed response that must wait for the explicit completed signal."

        with (
            patch("modules.core.src.utility_core_dom_query.count_messages", return_value=1),
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", side_effect=[None, response, response]),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 0.4, 0.5, 0.6]
            mock_time.sleep = MagicMock()

            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=120,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=1,
            )

        assert result == response

    def test_stable_text_without_terminal_event_is_not_accepted(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        response = "A response whose text is stable while Qwen is still generating."

        with (
            patch("modules.core.src.utility_core_dom_query.count_messages", return_value=1),
            patch(
                "modules.core.src.capabilities_stream_monitor._dom_latest",
                side_effect=[None, response, response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", side_effect=[False, False, True]),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 1, 2, 3, 4]
            mock_time.sleep = MagicMock()

            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=120,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=1,
            )

        assert result == response

    def test_emits_streaming_event_once_for_multiple_response_updates(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        first_text = "The first streamed response chunk is long enough."
        second_text = "The second streamed response chunk is also long enough."
        msg_side_effect = [None, first_text, second_text, second_text, second_text]

        with (
            patch("modules.core.src.utility_core_dom_query.count_messages", return_value=2),
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", side_effect=msg_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0] + [0.1] * 20
            mock_time.sleep = MagicMock()

            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=5,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=2,
            )

        assert result == second_text
        streaming_events = [
            call for call in emitter.emit.call_args_list if call.args and call.args[0] == EVENT_STREAMING_GENERATION
        ]
        assert len(streaming_events) == 1

    def test_returns_stable_text(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        stable_text = "This is a stable AI response with enough content to pass validation."

        # latest_message_text: first call sets baseline (return None), then return stable_text.
        # Without this, baseline_text == stable_text so text != baseline_text is always False
        # and the loop never processes any text, hanging until timeout.
        msg_side_effect = [None] + [stable_text] * 20

        with (
            patch("modules.core.src.utility_core_dom_query.count_messages", return_value=2),
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", side_effect=msg_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0] + [0.1] * 50
            mock_time.sleep = MagicMock()

            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=5,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=2,
            )
            assert result == stable_text

    def test_stall_detection_raises_stuck_error_when_no_forward_event(self):
        """No forward event (thinking, text change, or completion) for the
        stall window must raise StuckDetectedError — not a wall-clock
        ResponseDetectionTimeoutError."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with (
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            # The stall window (300s) trips well inside the 900s hard-cutoff
            # budget (issue #372) so the event-driven error surfaces, not the
            # wall-clock cutoff.
            mock_time.time.side_effect = [0, 300]
            mock_time.sleep = MagicMock()

            with pytest.raises(StuckDetectedError, match="Stuck detected"):
                StreamMonitor(stall_timeout_sec=300).wait_for_response(
                    page,
                    timeout_sec=900,
                    msg_count_before=1,
                    emitter=emitter,
                    polling_interval_sec=0,
                )

    def test_slow_generation_stays_alive_as_long_as_text_changes(self):
        """A slow-but-alive generation that keeps emitting forward events
        (text changes) must never trip the stall detector, even when
        elapsed wall time far exceeds the stall threshold."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        # Text changes every ~250s (below the 300s stall window). Total
        # elapsed time reaches 1000s — far beyond the stall threshold but
        # inside the 3600s hard-cutoff budget (issue #372) — and each text
        # change resets the forward-event clock.
        text_side_effect = [
            None,
            "chunk 1 with enough text",
            "chunk 2 with enough text",
            "chunk 3 with enough text",
            "final answer with enough text",
            "final answer with enough text",
            "final answer with enough text",
        ]
        time_calls = [0, 250, 500, 750, 1000, 1000, 1000]

        with (
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", side_effect=text_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = time_calls
            mock_time.sleep = MagicMock()

            result = StreamMonitor(stall_timeout_sec=300).wait_for_response(
                page,
                timeout_sec=3600,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=2,
            )
            assert result == "final answer with enough text"


class TestResponseExtractionContract:
    def test_js_extraction_excludes_page_shell_fallback(self):
        assert ".response-message-content" in JS_GET_RESPONSE_TEXT
        assert ".qwen-markdown-text" in JS_GET_RESPONSE_TEXT
        assert "document.querySelectorAll('div, p, pre, section, article, main')" not in JS_GET_RESPONSE_TEXT
        assert "qwen-chat-message-assistant" in JS_GET_RESPONSE_TEXT
        assert "chat-message-assistant" in JS_GET_RESPONSE_TEXT


class TestPreSendBaseline:
    def test_detects_response_when_first_poll_already_has_new_text(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        baseline = "Previous assistant answer"
        response = "A newly generated response that is already rendered before polling starts."

        with (
            patch("modules.core.src.utility_core_dom_query.count_messages", return_value=2),
            patch(
                "modules.core.src.capabilities_stream_monitor._dom_latest",
                side_effect=[response, response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 0.1, 0.2, 0.3, 0.4]
            mock_time.sleep = MagicMock()
            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=5,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=2,
                baseline_text=baseline,
            )

        assert result == response
        event_names = [call.args[0] for call in emitter.emit.call_args_list]
        assert EVENT_STREAMING_GENERATION in event_names
        assert EVENT_GENERATION_FINISHED in event_names


class TestHardResponseTimeout:
    """Issue #372: timeout_sec is a hard cutoff, not an observability hint."""

    def test_hard_cutoff_raises_at_timeout_sec(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with (
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            # wall clock jumps past the 120s budget while the 4h safety
            # breaker and the 5min stall window are nowhere near tripping.
            mock_time.time.side_effect = [0, 121]
            mock_time.sleep = MagicMock()

            with pytest.raises(ResponseDetectionTimeoutError, match="hard timeout"):
                StreamMonitor().wait_for_response(
                    page,
                    timeout_sec=120,
                    msg_count_before=1,
                    emitter=emitter,
                    polling_interval_sec=0,
                )

    def test_safety_breaker_wins_when_both_trip_same_poll(self):
        """The absolute backstop message must win if both budgets trip together."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with (
            patch("modules.core.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.core.src.capabilities_stream_monitor.time") as mock_time,
        ):
            mock_time.time.side_effect = [0, 14_400]
            mock_time.sleep = MagicMock()

            with pytest.raises(ResponseDetectionTimeoutError, match="circuit breaker"):
                StreamMonitor(safety_timeout_sec=14_400).wait_for_response(
                    page,
                    timeout_sec=120,
                    msg_count_before=1,
                    emitter=emitter,
                    polling_interval_sec=0,
                )
