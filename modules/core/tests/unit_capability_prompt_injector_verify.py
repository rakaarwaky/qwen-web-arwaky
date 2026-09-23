"""Tests for prompt_injector.py — remaining uncovered lines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error

from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import PromptInjectionError


class TestVerifyInjectionExtended:
    def test_verify_numeric_value(self):
        el = MagicMock()
        el.evaluate.return_value = 0
        assert PromptInjector()._verify_injection(el) is False

    def test_verify_list_value(self):
        el = MagicMock()
        el.evaluate.return_value = ["text"]
        assert PromptInjector()._verify_injection(el) is True

    def test_verify_empty_list(self):
        el = MagicMock()
        el.evaluate.return_value = []
        assert PromptInjector()._verify_injection(el) is False


class TestInjectTextExtended:
    def test_react_strategy_js_exception(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        # React JS raises Error
        page.evaluate.side_effect = Error("script error")
        # fill works
        PromptInjector().inject_text(page, "text via fill")
        el.fill.assert_called_once()

    def test_react_strategy_verification_fails(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        # React inject returns True, but verification returns empty
        # This causes strategies to fail verification
        el.evaluate.return_value = ""
        page.evaluate.side_effect = [True]  # react inject
        with pytest.raises(PromptInjectionError, match="All strategies executed but input verification failed"):
            PromptInjector().inject_text(page, "text via fill")

    def test_focus_failure_before_inject(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        el.focus.side_effect = Error("disconnected")
        page.evaluate.side_effect = [True]  # React succeeds despite focus fail
        PromptInjector().inject_text(page, "text after focus fail")
