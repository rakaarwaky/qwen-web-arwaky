"""Tests for sender.py — remaining uncovered lines in click_send, count_messages, latest_message_text."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.shared.src import LifecycleEmitter, SendDispatchError
from modules.shared.src.taxonomy_core_vo import ClickTimeoutMs, SenderConfig


def _sender() -> SendDispatcher:
    # Tiny timeout so the no-selector fallback path doesn't wait the full default.
    return SendDispatcher(click_timeout_ms=ClickTimeoutMs(100))


class TestClickSendExtended:
    def test_document_parsed_false_raises(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(SendDispatchError, match="document attachment parsing"):
            _sender().click_send(page, emitter, document_parsed=False)

    def test_no_visible_selector_uses_enter_fallback(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        # No visible send button (first.count=0) → Enter fallback used.
        # The dispatch ACK must come from a real new user turn (message count 2
        # after the baseline count 1), not from a cleared composer/disabled UI.
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.count.return_value = 0
        loc.first.is_visible.return_value = False
        loc.nth.return_value.evaluate.return_value = False
        loc.nth.return_value.text_content.return_value = None
        page.locator.return_value = loc
        page.evaluate.side_effect = [1, "", 2]
        page.keyboard.press = MagicMock()

        _sender().click_send(page, emitter)
        page.keyboard.press.assert_called_once_with("Enter")
        assert emitter.emit.call_count == 2

    def test_changed_message_text_acknowledges_when_count_is_unchanged(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.count.return_value = 1
        loc.first.is_visible.return_value = True
        loc.first.is_enabled.return_value = True
        loc.nth.return_value.evaluate.return_value = False
        loc.nth.return_value.text_content.return_value = None
        page.locator.return_value = loc
        page.evaluate.side_effect = [1, "before", 1, "after"]

        _sender().click_send(page, emitter)

        assert emitter.emit.call_count == 2

    def test_click_send_with_config_keyword_arg(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        loc = MagicMock()
        loc.count.return_value = 1
        loc.first.count.return_value = 0
        loc.first.is_visible.return_value = False
        loc.nth.return_value.evaluate.return_value = False
        loc.nth.return_value.text_content.return_value = None
        page.locator.return_value = loc
        page.evaluate.side_effect = [1, "", 2]
        page.keyboard.press = MagicMock()

        cfg = SenderConfig(click_timeout_ms=100, try_enter_key_fallback=True)
        _sender().click_send(page, emitter, config=cfg)
        page.keyboard.press.assert_called_once_with("Enter")

    def test_selector_exception_continues(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        call_count = [0]

        def locator_factory(sel):
            call_count[0] += 1
            loc = MagicMock()
            if call_count[0] == 1:
                raise Error("disconnected")
            loc.count.return_value = 1
            loc.first.count.return_value = 1
            loc.first.is_visible.return_value = True
            loc.first.is_enabled.return_value = True
            loc.nth.return_value.evaluate.return_value = False
            loc.nth.return_value.text_content.return_value = None
            return loc

        page.locator.side_effect = locator_factory

        evaluate_count = [0]

        def evaluate_factory(script, *args, **kwargs):
            evaluate_count[0] += 1
            if "turns" in script:
                return 1
            if evaluate_count[0] <= 2:
                return ""
            return "new response"

        page.evaluate.side_effect = evaluate_factory

        with (
            patch("modules.core.src.capabilities_send_dispatcher._is_file_card_parsing", return_value=False),
            patch("modules.core.src.capabilities_send_dispatcher._is_parse_toast_visible", return_value=False),
        ):
            _sender().click_send(page, emitter)
        assert emitter.emit.call_count == 2


class TestCountMessagesExtended:
    def test_js_evaluate_returns_non_int(self):
        page = MagicMock()
        page.evaluate.return_value = "not_an_int"
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = count_messages(page)
        assert isinstance(result, int)

    def test_js_evaluate_exception_fallback(self):
        page = MagicMock()
        page.evaluate.side_effect = Error("crashed")
        loc = MagicMock()
        loc.count.return_value = 3
        page.locator.return_value = loc
        result = count_messages(page)
        assert result == 3

    def test_both_methods_fail(self):
        page = MagicMock()
        page.evaluate.side_effect = Error("crashed")
        page.locator.side_effect = Error("crashed")
        result = count_messages(page)
        assert result == 0


class TestLatestMessageTextExtended:
    def test_js_returns_empty(self):
        page = MagicMock()
        page.evaluate.return_value = ""
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result is None

    def test_js_evaluate_exception_fallback(self):
        page = MagicMock()
        page.evaluate.side_effect = Error("crashed")
        loc = MagicMock()
        loc.count.return_value = 1
        loc.last.text_content.return_value = "  answer  "
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result == "answer"

    def test_both_methods_fail(self):
        page = MagicMock()
        page.evaluate.side_effect = Error("crashed")
        page.locator.side_effect = Error("crashed")
        result = latest_message_text(page)
        assert result is None


def test_composer_reset_alone_is_not_dispatch_ack():
    page = MagicMock()
    emitter = MagicMock(spec=LifecycleEmitter)
    loc = MagicMock()
    loc.count.return_value = 1
    loc.first.count.return_value = 0
    loc.first.is_visible.return_value = False
    loc.first.is_enabled.return_value = False
    loc.first.input_value.return_value = ""
    loc.nth.return_value.evaluate.return_value = False
    loc.nth.return_value.text_content.return_value = None
    page.locator.return_value = loc
    page.evaluate.return_value = 1
    page.keyboard.press = MagicMock()

    with pytest.raises(SendDispatchError, match="did not acknowledge the user turn"):
        _sender().click_send(page, emitter)


def _page_with_no_send_selector() -> MagicMock:
    page = MagicMock()

    def locator_factory(_selector):
        loc = MagicMock()
        loc.count.return_value = 0
        loc.first.count.return_value = 0
        loc.first.is_visible.return_value = False
        loc.nth.return_value.evaluate.return_value = False
        loc.nth.return_value.text_content.return_value = None
        return loc

    page.locator.side_effect = locator_factory
    return page


def test_no_visible_selector_does_not_press_enter_when_instance_fallback_disabled():
    page = _page_with_no_send_selector()
    emitter = MagicMock(spec=LifecycleEmitter)

    with pytest.raises(SendDispatchError, match="send button and Enter fallback"):
        SendDispatcher(try_enter_key_fallback=False, click_timeout_ms=ClickTimeoutMs(100)).click_send(page, emitter)

    page.keyboard.press.assert_not_called()
    emitter.emit.assert_not_called()


def test_per_call_sender_config_overrides_instance_fallback():
    page = _page_with_no_send_selector()
    emitter = MagicMock(spec=LifecycleEmitter)
    config = SenderConfig(try_enter_key_fallback=False)

    with pytest.raises(SendDispatchError, match="send button and Enter fallback"):
        SendDispatcher(try_enter_key_fallback=True, click_timeout_ms=ClickTimeoutMs(100)).click_send(
            page, emitter, config=config
        )

    page.keyboard.press.assert_not_called()
    emitter.emit.assert_not_called()
