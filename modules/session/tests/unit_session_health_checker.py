"""Unit tests for the real, browser-backed SessionHealthChecker.

These pin the contract that ``check_session`` drives the injected browser
seam (``health_probe_page``), that an authenticated, non-rate-limited page
reports healthy, that a rate-limit banner or a missing composer reports
unhealthy, and that a session whose profile no longer authenticates
(``AuthRequiredError``) reports unhealthy instead of forever-"pong".
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
from modules.shared.src.taxonomy_core_error import AuthRequiredError
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionStatus


def _session(index: int = 0) -> SessionInfo:
    return SessionInfo(
        session_id=f"unit-{index}",
        name=f"session-{index}",
        path=Path(f"/tmp/session-{index}"),
        status=SessionStatus.UNKNOWN,
        created_at=datetime(2026, 1, 1),
    )


def _page_mock(*, body: str = "", usable: bool = True) -> MagicMock:
    page = MagicMock()
    page.inner_text.return_value = body
    page.query_selector.return_value = MagicMock() if usable else None
    page.wait_for_timeout.return_value = None
    return page


class _FakeBrowser:
    """Protocol-shaped browser seam that yields a canned page without Playwright."""

    def __init__(self, page: Any, raise_auth: bool = False) -> None:
        self._page = page
        self._raise_auth = raise_auth

    @contextmanager
    def health_probe_page(self, cfg: Any) -> Iterator[Any]:
        if self._raise_auth:
            raise AuthRequiredError("Session expired — saved profile no longer authenticates.")
        yield self._page


def _checker(page: Any, *, raise_auth: bool = False, timeout_seconds: float = 5.0) -> SessionHealthChecker:
    return SessionHealthChecker(browser=_FakeBrowser(page, raise_auth=raise_auth), timeout_seconds=timeout_seconds)


def test_check_session_is_healthy_on_a_clean_authenticated_chat_page() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    assert asyncio.run(_checker(page).check_session(_session())) is True


def test_check_session_is_unhealthy_when_body_shows_a_rate_limit_notice() -> None:
    page = _page_mock(body="You have reached the daily limit. Please try again tomorrow.", usable=True)
    assert asyncio.run(_checker(page).check_session(_session())) is False


def test_check_session_is_unhealthy_when_the_chat_composer_is_missing() -> None:
    page = _page_mock(body="Qwen chat", usable=False)
    assert asyncio.run(_checker(page).check_session(_session())) is False


def test_check_session_is_unhealthy_when_the_profile_no_longer_authenticates() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    assert asyncio.run(_checker(page, raise_auth=True).check_session(_session())) is False


def test_check_session_without_a_browser_seam_is_unhealthy() -> None:
    """An inert checker (no browser injected) must report unhealthy, not crash."""
    assert asyncio.run(SessionHealthChecker().check_session(_session())) is False
