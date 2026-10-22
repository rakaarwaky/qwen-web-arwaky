"""Utility: browser session liveness and auth probe.

Module-level helpers only (utility layer). Used by BrowserAdapter and tests.
"""

from __future__ import annotations

import logging

from playwright.sync_api import Error, Page

from modules.shared.src.common import utility_dom_helper
from modules.shared.src.common.taxonomy_core_constant import (
    AUTH_KEYWORDS,
    LOGIN_FORM_SELECTORS,
    SESSION_EXPIRED_BANNER_SELECTORS,
    SESSION_EXPIRED_KEYWORDS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError

log = logging.getLogger("utility_browser_session_check")


def session_is_alive(page: Page) -> bool:
    """Return True if the session is stable and the chat UI is responsive."""
    try:
        ready = page.evaluate("() => document.readyState")
        if ready != "complete":
            log.warning("session_check_failed %s %s", "page_not_ready", ready)
            return False
        if not page.query_selector(TEXTAREA_SELECTOR):
            log.warning("session_check_failed %s", "textarea_missing")
            return False
        return True
    except Error as exc:
        log.warning("session_check_failed %s %s", "playwright_error", str(exc))
        return False
    except Exception as exc:
        log.warning("session_check_failed %s %s", "unexpected_error", str(exc))
        return False


def assert_on_chat_page(page: Page, strict: bool = True) -> None:
    """Raise AuthRequiredError if the page is a login/auth/guest page."""
    current_url = page.url.lower()
    if any(k in current_url for k in AUTH_KEYWORDS):
        raise AuthRequiredError(
            f"Not authenticated — browser is on login or guest page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )
    combined_login = ", ".join(LOGIN_FORM_SELECTORS)
    if utility_dom_helper.is_any_visible(page, combined_login):
        raise AuthRequiredError(
            f"Not authenticated — login form/button detected on page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )
    if not page.query_selector(TEXTAREA_SELECTOR):
        if strict:
            log.warning("chat_textarea_missing_but_no_login_form_detected %s", page.url)
        else:
            log.info("chat_textarea_missing_but_no_login_form_detected %s", page.url)
    if _in_page_expiry_banner_visible(page):
        raise AuthRequiredError(
            "Session expired — the saved Qwen login session is no longer valid "
            f"(in-page notice detected on {page.url}). "
            "Run `qwen-web-arwaky session login` to re-authenticate, then retry.",
            session_expired=True,
        )


def _in_page_expiry_banner_visible(page: Page) -> bool:
    """True when the live page shows an in-page session-expiry notice."""
    try:
        body_text = page.inner_text("body")
        lowered = str(body_text or "").lower()
        if any(kw in lowered for kw in SESSION_EXPIRED_KEYWORDS):
            return True
        if utility_dom_helper.is_any_visible(page, ", ".join(SESSION_EXPIRED_BANNER_SELECTORS)):
            return True
    except (Error, TypeError):
        return False
    return False


__all__ = ["session_is_alive", "assert_on_chat_page"]
