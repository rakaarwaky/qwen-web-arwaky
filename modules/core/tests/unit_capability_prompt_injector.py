"""Regression tests for prompt_injector module — _verify_injection, custom InjectorConfig, strategy fallbacks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error, TimeoutError

from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import (
    DEFAULT_INJECTOR_CONFIG,
    ElementNotFoundError,
    InjectorConfig,
    PromptInjectionError,
)

# ─── _verify_injection ─────────────────────────────────────────────────────


class TestVerifyInjection:
    def test_verify_with_value_attribute(self):
        el = MagicMock()
        el.evaluate.return_value = "injected text"
        assert PromptInjector()._verify_injection(el) is True

    def test_verify_empty_value(self):
        el = MagicMock()
        el.evaluate.return_value = ""
        assert PromptInjector()._verify_injection(el) is False

    def test_verify_none_value(self):
        el = MagicMock()
        el.evaluate.return_value = None
        assert PromptInjector()._verify_injection(el) is False

    def test_verify_whitespace_only(self):
        el = MagicMock()
        el.evaluate.return_value = "   "
        assert PromptInjector()._verify_injection(el) is False

    def test_verify_exception(self):
        el = MagicMock()
        el.evaluate.side_effect = Exception("disconnected")
        assert PromptInjector()._verify_injection(el) is False


# ─── find_input with custom config ─────────────────────────────────────────


class TestFindInputCustomConfig:
    def test_custom_selectors_tried_in_order(self):
        page = MagicMock()
        el = MagicMock()

        cfg = InjectorConfig(input_selectors=["#first", "#second", "#third"])

        # First two fail, third succeeds
        def wait_side_effect(sel, state=None, timeout=None):
            if sel == "#third":
                return el
            raise TimeoutError("not found")

        page.wait_for_selector.side_effect = wait_side_effect

        result = PromptInjector().find_input(page, config=cfg)
        assert result == el

    def test_all_custom_selectors_fail_uses_primary(self):
        page = MagicMock()
        el = MagicMock()
        primary = "#primary-selector"

        cfg = InjectorConfig(input_selectors=[primary], wait_timeout_ms=5000)

        call_count = [0]

        def wait_side_effect(sel, state=None, timeout=None):
            call_count[0] += 1
            # First call: short timeout per-selector attempt
            # Second call: full timeout on primary
            if call_count[0] >= 2:
                return el
            raise TimeoutError("not found")

        page.wait_for_selector.side_effect = wait_side_effect
        result = PromptInjector().find_input(page, config=cfg)
        assert result == el

    def test_all_selectors_fail_raises(self):
        page = MagicMock()
        page.wait_for_selector.side_effect = TimeoutError("timeout")

        cfg = InjectorConfig(input_selectors=["#x"], wait_timeout_ms=50)
        with pytest.raises(ElementNotFoundError):
            PromptInjector().find_input(page, config=cfg)


# ─── inject_text with strategy fallbacks ────────────────────────────────────


class TestInjectTextStrategies:
    def test_react_strategy_success(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        # Force Playwright fill to fail so the React value-setter (page.evaluate)
        # strategy is exercised.
        el.fill.side_effect = Error("fill failed")
        page.evaluate.side_effect = [True]  # react inject success

        PromptInjector().inject_text(page, "Hello Qwen")
        assert page.evaluate.call_count >= 1

    def test_fallback_to_type(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        # fill fails, JS fails, type succeeds
        el.fill.side_effect = Error("fill broken")
        page.evaluate.return_value = False

        PromptInjector().inject_text(page, "Type fallback text")
        el.type.assert_called_once()

    def test_all_strategies_fail_raises(self):
        page = MagicMock()
        el = MagicMock()
        page.wait_for_selector.return_value = el
        page.evaluate.side_effect = [False, False]
        el.fill.side_effect = Error("broken")
        el.type.side_effect = Error("broken")

        with pytest.raises(PromptInjectionError, match="All strategies failed for prompt"):
            PromptInjector().inject_text(page, "failing")

    def test_empty_text_raises(self):
        page = MagicMock()
        with pytest.raises(PromptInjectionError, match="empty"):
            PromptInjector().inject_text(page, "")

    def test_whitespace_only_raises(self):
        page = MagicMock()
        with pytest.raises(PromptInjectionError, match="empty"):
            PromptInjector().inject_text(page, "   \n  ")


# ─── InjectorConfig defaults ───────────────────────────────────────────────


class TestInjectorConfigDefaults:
    def test_default_config_has_selectors(self):
        cfg = DEFAULT_INJECTOR_CONFIG
        assert len(cfg.input_selectors) > 0

    def test_default_timeout(self):
        cfg = InjectorConfig()
        assert cfg.wait_timeout_ms == 10_000

    def test_custom_config(self):
        cfg = InjectorConfig(
            input_selectors=["#custom"],
            wait_timeout_ms=5000,
            typing_delay_ms=50,
            verify_injection=False,
        )
        assert cfg.input_selectors == ["#custom"]
        assert cfg.wait_timeout_ms == 5000
        assert cfg.typing_delay_ms == 50
        assert cfg.verify_injection is False
