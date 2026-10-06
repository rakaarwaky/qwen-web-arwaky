"""Smoke tests for the browser session probe.

The probe runs against a stub page, so no browser build, no network, and no
saved session are needed. These pin the readiness and authentication checks
that every pipeline run depends on before it sends a prompt.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.browser.src.capabilities_browser_adapter import SessionCheck
from modules.shared.src.taxonomy_core_constant import TEXTAREA_SELECTOR
from modules.shared.src.taxonomy_core_error import AuthRequiredError


def _ready_page() -> MagicMock:
    page = MagicMock()
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    page.url = "https://chat.qwen.ai/"
    page.locator.return_value.count.return_value = 0
    return page


def _login_page() -> MagicMock:
    page = _ready_page()
    page.url = "https://chat.qwen.ai/login"
    return page


def test_smoke_ready_page_reads_alive() -> None:
    assert SessionCheck(_ready_page()).is_alive() is True


def test_smoke_unready_page_reads_not_alive() -> None:
    page = _ready_page()
    page.evaluate.return_value = "loading"
    assert SessionCheck(page).is_alive() is False


def test_smoke_missing_textarea_reads_not_alive() -> None:
    page = _ready_page()
    page.query_selector.return_value = None
    assert SessionCheck(page).is_alive() is False


def test_smoke_login_redirect_raises_auth_required() -> None:
    with pytest.raises(AuthRequiredError):
        SessionCheck(_login_page()).check_auth()


def test_smoke_probe_queries_the_pinned_textarea_selector() -> None:
    page = _ready_page()
    SessionCheck(page).is_alive()
    page.query_selector.assert_any_call(TEXTAREA_SELECTOR)
