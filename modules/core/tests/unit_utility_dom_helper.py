from unittest.mock import MagicMock

from modules.core.src.utility_core_dom_helper import click_send
from modules.shared.src.taxonomy_core_vo import SenderConfig


def test_click_send_explicit_timeout_overrides_config() -> None:
    page = MagicMock()
    locator = page.locator.return_value.first
    locator.is_visible.return_value = True
    config = SenderConfig(click_timeout_ms=5000, try_enter_key_fallback=False)

    assert click_send(page, config, timeout_ms=7000) is True
    locator.is_visible.assert_called_once_with(timeout=7000)
    locator.click.assert_called_once_with()


def test_click_send_uses_config_timeout_when_not_explicit() -> None:
    page = MagicMock()
    locator = page.locator.return_value.first
    locator.is_visible.return_value = True
    config = SenderConfig(click_timeout_ms=5000, try_enter_key_fallback=False)

    assert click_send(page, config) is True
    locator.is_visible.assert_called_once_with(timeout=5000)
