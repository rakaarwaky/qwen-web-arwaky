"""Unit tests for session verdict classification across the two checkers.

Pins the locked decisions:
- Login checker: ACTIVE only from a successful authenticated probe,
  AUTH_REQUIRED for any other failed probe (expired profile, missing
  composer, launch failure, probe error).
- Limit checker: ACTIVE when the page replies without a limit banner,
  LIMITED from observed provider-limit evidence, a probe timeout, or a
  probe failure. A transient failure on a confirmed LIMITED session keeps
  it LIMITED.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_limit_checker import SessionLimitChecker
from modules.session.src.capabilities_session_login_checker import SessionLoginChecker
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.session.taxonomy_session_vo import (
    HealthReason,
    SessionInfo,
    SessionStatus,
)


def _session(
    index: int = 0, status: SessionStatus = SessionStatus.AUTH_REQUIRED, reason: str | None = None
) -> SessionInfo:
    return SessionInfo(
        session_id=f"health-{index}",
        name=f"session-{index}",
        path=Path(f"/tmp/health-{index}"),
        status=status,
        created_at=datetime(2026, 1, 1),
        reason=reason,
    )


def _page_mock(*, body: str = "", usable: bool = True) -> MagicMock:
    page = MagicMock()
    page.inner_text.return_value = body
    page.evaluate.return_value = "complete"
    page.url = "https://chat.qwen.ai/"
    page.query_selector.return_value = MagicMock() if usable else None
    page.wait_for_timeout.return_value = None
    loc = page.locator.return_value
    loc.count.return_value = 0
    loc.first.is_visible.return_value = False
    return page


class _FakeBrowser:
    def __init__(self, page: Any, raise_auth: bool = False, raise_error: type[Exception] | None = None) -> None:
        self._page = page
        self._raise_auth = raise_auth
        self._raise_error = raise_error

    @contextmanager
    def health_probe_page(self, cfg: Any):
        if self._raise_auth:
            raise AuthRequiredError("Session expired")
        if self._raise_error:
            raise self._raise_error("probe failed")
        yield self._page


def _login_checker(page: Any, **kwargs: Any) -> SessionLoginChecker:
    return SessionLoginChecker(browser_lifecycle=_FakeBrowser(page, **kwargs), timeout_seconds=5.0)


def _limit_checker(page: Any, **kwargs: Any) -> SessionLimitChecker:
    return SessionLimitChecker(browser_lifecycle=_FakeBrowser(page, **kwargs), timeout_seconds=5.0)


# ── Login checker verdicts ──────────────────────────────────────────────────


def test_active_from_successful_authenticated_probe() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    verdict = asyncio.run(_login_checker(page).check_session(_session()))
    assert verdict.status == SessionStatus.ACTIVE
    assert verdict.is_healthy
    assert verdict.reason is None


def test_auth_required_from_expired_profile() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    verdict = asyncio.run(_login_checker(page, raise_auth=True).check_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.EXPIRED.value
    assert verdict.recovery_action is not None


def test_auth_required_from_composer_missing() -> None:
    page = _page_mock(body="Qwen chat", usable=False)
    verdict = asyncio.run(_login_checker(page).check_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.EXPIRED.value


def test_browser_not_configured_returns_auth_required() -> None:
    verdict = asyncio.run(SessionLoginChecker().check_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.LAUNCH_FAILURE.value


# ── Limit checker verdicts ──────────────────────────────────────────────────


def test_limited_from_rate_limit_banner() -> None:
    page = _page_mock(body="You have reached the daily limit. Please try again tomorrow.", usable=True)
    verdict = asyncio.run(_limit_checker(page).check_session(_session()))
    assert verdict.status == SessionStatus.LIMITED
    assert verdict.reason == HealthReason.QUOTA.value


def test_active_from_healthy_page() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    verdict = asyncio.run(_limit_checker(page).check_session(_session()))
    assert verdict.status == SessionStatus.ACTIVE
    assert verdict.is_healthy


def test_limited_when_composer_unreachable() -> None:
    """A page whose composer is unreachable is treated as a limit signal."""
    page = _page_mock(body="Qwen chat", usable=False)
    verdict = asyncio.run(_limit_checker(page).check_session(_session()))
    assert verdict.status == SessionStatus.LIMITED


def test_limited_not_overwritten_by_transient_failure() -> None:
    """A transient probe failure on a LIMITED session must keep it LIMITED."""
    page = _page_mock(body="Qwen chat", usable=True)
    limited_session = _session(status=SessionStatus.LIMITED, reason="QUOTA")
    verdict = asyncio.run(_limit_checker(page, raise_error=ConnectionError).check_session(limited_session))
    assert verdict.status == SessionStatus.LIMITED
    assert verdict.reason == "QUOTA"


def test_browser_not_configured_returns_limited_for_limit_checker() -> None:
    verdict = asyncio.run(SessionLimitChecker().check_session(_session()))
    assert verdict.status == SessionStatus.LIMITED
