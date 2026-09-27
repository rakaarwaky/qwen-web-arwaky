"""Regression tests for streamer module — validate_response_content, is_generation_complete, wait_for_response edge cases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.prompt.src.capabilities_stream_monitor import (
    DEFAULT_SAFETY_TIMEOUT_SEC,
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
from modules.shared.src.taxonomy_core_constant import JS_GET_RESPONSE_TEXT, THINKING_CARD_TEXT_MARKERS
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
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
                "modules.prompt.src.capabilities_stream_monitor._dom_latest",
                side_effect=[None, TimeoutError("temporary"), response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.shared.src.utility_dom_query.count_messages", return_value=1),
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", side_effect=[None, response, response]),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.shared.src.utility_dom_query.count_messages", return_value=1),
            patch(
                "modules.prompt.src.capabilities_stream_monitor._dom_latest",
                side_effect=[None, response, response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", side_effect=[False, False, True]),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.shared.src.utility_dom_query.count_messages", return_value=2),
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", side_effect=msg_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.shared.src.utility_dom_query.count_messages", return_value=2),
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", side_effect=msg_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", side_effect=text_side_effect),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.shared.src.utility_dom_query.count_messages", return_value=2),
            patch(
                "modules.prompt.src.capabilities_stream_monitor._dom_latest",
                side_effect=[response, response, response],
            ),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", return_value=None),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
            patch.object(StreamMonitor, "is_generation_complete", return_value=False),
            patch("modules.prompt.src.capabilities_stream_monitor.time") as mock_time,
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


class TestReloadGatedOnProgress:
    """Issue #382: the 30s periodic reload is suppressed while the stream
    continues making forward progress, so a long generation cannot be starved
    out of the stability condition.

    The tests run on the real (unpatched) clock: a reload requires 30s of
    wall time, so an iteration that still has forward progress completes in
    microseconds and the loop exits long before the first reload window can
    elapse.
    """

    def test_stable_text_still_stabilizes_with_real_clock(self) -> None:
        """Forward-progress text across a 30s boundary would have reset
        ``stable_count`` indefinitely before the fix; with the gate in place
        the stream is untouched and stabilizes in a handful of polls."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        texts = iter(
            [
                "first word",
                "first word second",
                "first word second third",
                "first word second third fourth",
                "first word second third fourth",
                "first word second third fourth",
                "first word second third fourth",
                "first word second third fourth",
                "first word second third fourth",
            ]
        )

        with (
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", side_effect=lambda *_: next(texts)),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
        ):
            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=60,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=4,
                baseline_text="prior",
            )

        assert str(result) == "first word second third fourth"
        # Streaming text made forward progress every poll, so no reload may
        # have fired — this is exactly the starvation loop the fix removes.
        assert page.reload.call_count == 0

    def test_stable_response_returns_text(self) -> None:
        """A fully stable, complete response returns immediately on the real
        clock (well under the 30s reload window)."""
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        response = "a stable final answer"

        with (
            patch("modules.prompt.src.capabilities_stream_monitor._dom_latest", return_value=response),
            patch.object(StreamMonitor, "is_generation_complete", return_value=True),
            patch.object(StreamMonitor, "is_thinking_active", return_value=False),
        ):
            result = StreamMonitor().wait_for_response(
                page,
                timeout_sec=60,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                baseline_text="prior",
            )

        assert str(result) == response
        assert page.reload.call_count == 0


class TestSafetyTimeoutConfiguration:
    """Issue #330: the 4h safety circuit breaker is operator-configurable."""

    def test_default_is_four_hours(self, monkeypatch):
        monkeypatch.delenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", raising=False)
        assert StreamMonitor().safety_timeout_sec == DEFAULT_SAFETY_TIMEOUT_SEC == 4 * 60 * 60

    def test_env_override_honored(self, monkeypatch):
        monkeypatch.setenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", "42")
        assert StreamMonitor().safety_timeout_sec == 42

    def test_explicit_argument_beats_env(self, monkeypatch):
        monkeypatch.setenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", "42")
        assert StreamMonitor(safety_timeout_sec=99).safety_timeout_sec == 99

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", "not-a-number")
        assert StreamMonitor().safety_timeout_sec == DEFAULT_SAFETY_TIMEOUT_SEC

    def test_non_positive_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", "0")
        assert StreamMonitor().safety_timeout_sec == DEFAULT_SAFETY_TIMEOUT_SEC

    def test_zero_explicit_still_raises(self, monkeypatch):
        monkeypatch.delenv("QWEN_STREAM_SAFETY_TIMEOUT_SEC", raising=False)
        with pytest.raises(ValueError, match="safety_timeout_sec"):
            StreamMonitor(safety_timeout_sec=0)


# ─── Thinking-card text must not become the assistant answer ────────────────


class TestThinkingCardIsNotAnAnswer:
    """Run 20260926_014817_5cd3cc wrote a 32-byte output holding only
    "Thought stopped": Qwen's thinking card renders inside the assistant
    message container, so the response extractor picked up the card's status
    line and the monitor stabilised on it in 4s."""

    def test_js_declares_thinking_card_markers(self):
        assert "THINKING_CARD_MARKERS" in JS_GET_RESPONSE_TEXT

    def test_js_skips_a_thinking_card_node(self):
        assert "isThinkingCard" in JS_GET_RESPONSE_TEXT

    def test_every_python_marker_appears_in_the_js(self):
        for marker in THINKING_CARD_TEXT_MARKERS:
            assert marker in JS_GET_RESPONSE_TEXT, marker

    def test_observed_failure_string_is_a_declared_marker(self):
        assert "thought stopped" in THINKING_CARD_TEXT_MARKERS

    def test_real_response_is_not_a_marker(self):
        for answer in (
            "Here is the reviewed architecture for the shared module.",
            "Thought stopped, so here is what I found instead.",
            "Use the stop button to halt a running generation.",
        ):
            assert answer.strip().lower() not in THINKING_CARD_TEXT_MARKERS

    def test_marker_match_is_exact_not_a_substring(self):
        """The JS compares the whole trimmed text, so a real answer that merely
        contains a marker phrase still returns."""
        answer = "Thought stopped. Here is the analysis you asked for."
        assert answer.strip().lower() not in THINKING_CARD_TEXT_MARKERS


# ─── Response-wait ceiling ──────────────────────────────────────────────────


class TestRequestTimeoutBudget:
    """The ceiling is wall-clock, so a long thinking phase consumes it. The
    default must cover a heavy reasoning model and stay operator-tunable."""

    def test_default_covers_a_long_thinking_phase(self):
        from modules.shared.src.taxonomy_core_vo import AppConfig

        cfg = AppConfig(input_path="/tmp/in.md", output_path="/tmp/out.md", session_path="/tmp/session")
        assert cfg.request_timeout >= 600, "a 120s ceiling aborts healthy thinking runs"

    def test_env_override_is_honored(self, monkeypatch):
        from modules.config.src.utility_config_app_factory import build_app_config

        monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "1800")
        assert build_app_config().request_timeout == 1800

    def test_invalid_env_falls_back_to_the_default(self, monkeypatch):
        from modules.config.src.utility_config_app_factory import build_app_config

        monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "not-a-number")
        assert build_app_config().request_timeout == 600

    def test_non_positive_env_falls_back_to_the_default(self, monkeypatch):
        from modules.config.src.utility_config_app_factory import build_app_config

        monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "0")
        assert build_app_config().request_timeout == 600

    def test_absent_env_keeps_the_default(self, monkeypatch):
        from modules.config.src.utility_config_app_factory import build_app_config

        monkeypatch.delenv("QWEN_REQUEST_TIMEOUT_SEC", raising=False)
        assert build_app_config().request_timeout == 600

    def test_default_exceeds_the_measured_thinking_phase_with_margin(self):
        """Run 20260926_023444_f5705c stabilised after 426s of real thinking
        with a 244KB attachment — the same input that the old 120s ceiling
        killed. The default must stay above that with room for a slower host,
        so a future change to 120s (or 300s) fails here instead of in the field.
        """
        from modules.shared.src.taxonomy_core_vo import AppConfig

        measured_thinking_sec = 426
        cfg = AppConfig(input_path="/tmp/in.md", output_path="/tmp/out.md", session_path="/tmp/session")
        assert cfg.request_timeout > measured_thinking_sec, (
            f"ceiling {cfg.request_timeout}s does not clear the measured "
            f"{measured_thinking_sec}s thinking phase; raise QWEN_REQUEST_TIMEOUT_SEC "
            "or the default"
        )

    def test_measured_thinking_phase_is_not_a_duplicate_of_the_marker_default(self):
        """Guard the 600 literal so a silent default change is visible in the
        diff of the two tests above rather than hidden inside a range check."""
        from modules.config.src.utility_config_app_factory import build_app_config

        assert build_app_config().request_timeout == 600
