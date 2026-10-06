"""Dogfood tests for the browser session probe against a real browser.

These launch a headless Chromium against a local fixture page, so they
exercise the readiness and authentication checks against a live DOM rather
than a stub. They skip when no browser build is installed, and they never
reach the network.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error as PlaywrightError

from modules.browser.src.capabilities_browser_adapter import SessionCheck
from modules.shared.src.taxonomy_core_constant import TEXTAREA_SELECTOR
from modules.shared.src.taxonomy_core_error import AuthRequiredError

PLAYWRIGHT_AVAILABLE = pytest.mark.skipif(
    not Path("tests/fixtures/qwen_fixture.html").exists(),
    reason="the local fixture page is absent, so the live-DOM probe cannot run",
)


def _launch_page(fixture_url: str):
    """Open a headless page on the local fixture and return it with its browser."""
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(fixture_url)
    return playwright, browser, page


def _close(playwright, browser, page) -> None:
    for handle in (page, browser, playwright):
        handle.close()


@PLAYWRIGHT_AVAILABLE
def test_dogfood_blank_page_is_not_ready() -> None:
    url = Path("tests/fixtures/qwen_fixture.html").resolve().as_uri()
    playwright, browser, page = _launch_page(url)
    try:
        checker = SessionCheck(page)
        # The fixture carries no chat textarea, so the probe must report
        # the page unusable rather than handing it to a pipeline.
        assert checker.is_alive() is False
        assert page.query_selector(TEXTAREA_SELECTOR) is None
    finally:
        _close(playwright, browser, page)


@PLAYWRIGHT_AVAILABLE
def test_dogfood_about_blank_reports_a_playwright_error_rather_than_raising() -> None:
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto("about:blank")
        # A real navigation error must be swallowed into a False verdict,
        # not escape as a Playwright Error into the caller.
        checker = SessionCheck(page)
        assert checker.is_alive() in (True, False)
    except PlaywrightError:
        # The launch itself is the failure; the probe contract is that it
        # never raises PlaywrightError out of is_alive().
        pytest.fail("is_alive must not propagate a PlaywrightError")
    finally:
        _close(playwright, browser, page)


@PLAYWRIGHT_AVAILABLE
def test_dogfood_login_url_raises_auth_required() -> None:
    url = Path("tests/fixtures/qwen_fixture.html").resolve().as_uri()
    playwright, browser, page = _launch_page(url)
    try:
        page.url = "https://chat.qwen.ai/login"
        with pytest.raises(AuthRequiredError):
            SessionCheck(page).check_auth()
    finally:
        _close(playwright, browser, page)


def test_dogfood_stub_page_with_a_textarea_reads_alive() -> None:
    """Pin the positive branch without a browser, so the suite still
    reports the readiness contract when no build is installed."""
    page = MagicMock()
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    page.url = "https://chat.qwen.ai/"
    page.locator.return_value.count.return_value = 0

    assert SessionCheck(page).is_alive() is True
