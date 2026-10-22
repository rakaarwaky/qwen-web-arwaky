"""Utility: browser session liveness and auth probe.

SessionCheck — page readiness + auth assertion used by BrowserAdapter and tests.
"""

from __future__ import annotations

from playwright.sync_api import Error, Page

from modules.shared.src.common.taxonomy_core_constant import (
    AUTH_KEYWORDS,
    LOGIN_FORM_SELECTORS,
    SESSION_EXPIRED_BANNER_SELECTORS,
    SESSION_EXPIRED_KEYWORDS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.utility_dom_helper import is_any_visible
from modules.shared.src.common.utility_logger_factory import get_logger

log = get_logger("capabilities_browser_session_check")

# Block 1: Class Definition & Constructor


class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        """Initialize with a Playwright Page instance."""
        self.page = page

    # Block 2: Protocol Method Implementation

    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive."""
        try:
            ready = self.page.evaluate("() => document.readyState")
            if ready != "complete":
                log.warning("session_check_failed %s %s", "page_not_ready", ready)
                return False

            if not self.page.query_selector(TEXTAREA_SELECTOR):
                log.warning("session_check_failed %s", "textarea_missing")
                return False

            return True
        except Error as exc:
            log.warning("session_check_failed %s %s", "playwright_error", str(exc))
            return False
        except Exception as exc:  # defensive fallback beyond playwright Error
            log.warning("session_check_failed %s %s", "unexpected_error", str(exc))
            return False

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated or UI is missing."""
        try:
            _assert_on_chat_page(self.page)
        except AuthRequiredError:
            raise
        except Error as exc:
            raise AuthRequiredError(f"Session invalid (browser error): {exc}") from exc

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of SessionCheck."""
        return f"SessionCheck(page={self.page!r})"


def _in_page_expiry_banner_visible(page: Page) -> bool:
    """True when the live page now shows an in-page session-expiry notice.

    Re-runs the banner text/selector scan from ``_assert_on_chat_page``
    against the CURRENT page state. Best-effort: a DOM that is unreadable
    (mid-hydration) is not a signal, so the method returns False rather
    than raising.
    """
    try:
        body_text = page.inner_text("body")
        lowered = str(body_text or "").lower()
        if any(kw in lowered for kw in SESSION_EXPIRED_KEYWORDS):
            return True
        if is_any_visible(page, ", ".join(SESSION_EXPIRED_BANNER_SELECTORS)):
            return True
    except (Error, TypeError):
        return False
    return False


def _assert_on_chat_page(page: Page, strict: bool = True) -> None:
    """Raise AuthRequiredError if the page is a login/auth/guest page (URL + DOM check).

    When ``strict=False`` (used right after the initial page load in
    ``navigate_to_chat`` where React may not have hydrated yet), a missing
    textarea without a login form is logged at ``info`` level instead of
    ``warning``; a missing textarea is a real signal in the steady-state
    session-check path (``strict=True``, the default).
    """
    current_url = page.url.lower()

    if any(k in current_url for k in AUTH_KEYWORDS):
        raise AuthRequiredError(
            f"Not authenticated — browser is on login or guest page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )

    combined_login = ", ".join(LOGIN_FORM_SELECTORS)
    if is_any_visible(page, combined_login):
        raise AuthRequiredError(
            f"Not authenticated — login form/button detected on page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )

    if not page.query_selector(TEXTAREA_SELECTOR):
        if strict:
            log.warning("chat_textarea_missing_but_no_login_form_detected %s", page.url)
        else:
            log.info("chat_textarea_missing_but_no_login_form_detected %s", page.url)

    # In-page session-expiry notice: Qwen sometimes keeps the chat URL and shows
    # an "Session expired, please login again" banner instead of redirecting.
    # The DOM may still be hydrating, so banner detection is best-effort — skip
    # on any read failure rather than mask a genuine auth problem.
    if _in_page_expiry_banner_visible(page):
        raise AuthRequiredError(
            "Session expired — the saved Qwen login session is no longer valid "
            f"(in-page notice detected on {page.url}). "
            "Run `qwen-web-arwaky session login` to re-authenticate, then retry.",
            session_expired=True,
        )


__all__ = ["SessionCheck", "_assert_on_chat_page", "_in_page_expiry_banner_visible"]
