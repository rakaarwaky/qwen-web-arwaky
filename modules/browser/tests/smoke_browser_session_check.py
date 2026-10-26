"""Smoke tests for the browser session probe.

The probe runs against a stub page, so no browser build, no network, and no
saved session are needed. These pin the readiness and authentication checks
that every pipeline run depends on before it sends a prompt.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.shared.src.browser import utility_browser_session_check as session_check_util
from modules.shared.src.common.taxonomy_core_constant import TEXTAREA_SELECTOR
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError


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
    assert session_check_util.session_is_alive(_ready_page()) is True


def test_smoke_unready_page_reads_not_alive() -> None:
    page = _ready_page()
    page.evaluate.return_value = "loading"
    assert session_check_util.session_is_alive(page) is False


def test_smoke_missing_textarea_reads_not_alive() -> None:
    page = _ready_page()
    page.query_selector.return_value = None
    assert session_check_util.session_is_alive(page) is False


def test_smoke_login_redirect_raises_auth_required() -> None:
    with pytest.raises(AuthRequiredError):
        session_check_util.assert_on_chat_page(_login_page())


def test_smoke_probe_queries_the_pinned_textarea_selector() -> None:
    page = _ready_page()
    session_check_util.session_is_alive(page)
    page.query_selector.assert_any_call(TEXTAREA_SELECTOR)
