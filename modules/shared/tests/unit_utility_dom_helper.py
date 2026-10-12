from unittest.mock import MagicMock

import pytest

from modules.shared.src.taxonomy_core_vo import SenderConfig
from modules.shared.src.utility_dom_helper import click_send


@pytest.mark.parametrize(
    ("explicit_timeout", "expected_timeout"),
    [(7000, 7000), (None, 5000)],
    ids=["explicit", "config"],
)
def test_click_send_timeout_selection(explicit_timeout: int | None, expected_timeout: int) -> None:
    """An explicit ``timeout_ms`` overrides the config timeout; when absent,
    the config value is used."""
    page = MagicMock()
    locator = page.locator.return_value.first
    locator.is_visible.return_value = True
    config = SenderConfig(click_timeout_ms=5000, try_enter_key_fallback=False)

    assert click_send(page, config, timeout_ms=explicit_timeout) is True
    locator.is_visible.assert_called_once_with(timeout=expected_timeout)
    locator.click.assert_called_once_with()
