"""Unit tests for session health verdict classification (BA-2-001).

Pins the locked decisions:
- ACTIVE only from a successful authenticated probe.
- LIMITED only from observed provider-limit evidence.
- AUTH_REQUIRED for any other failed probe.
- Probe failure MUST NOT overwrite a confirmed LIMITED verdict.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
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
    page.query_selector.return_value = MagicMock() if usable else None
    page.wait_for_timeout.return_value = None
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


def _checker(page: Any, **kwargs: Any) -> SessionHealthChecker:
    return SessionHealthChecker(browser=_FakeBrowser(page, **kwargs), timeout_seconds=5.0)


def test_active_from_successful_authenticated_probe() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    verdict = asyncio.run(_checker(page).diagnose_session(_session()))
    assert verdict.status == SessionStatus.ACTIVE
    assert verdict.is_healthy
    assert verdict.reason is None


def test_limited_from_rate_limit_banner() -> None:
    page = _page_mock(body="You have reached the daily limit. Please try again tomorrow.", usable=True)
    verdict = asyncio.run(_checker(page).diagnose_session(_session()))
    assert verdict.status == SessionStatus.LIMITED
    assert verdict.reason == HealthReason.QUOTA.value


def test_auth_required_from_expired_profile() -> None:
    page = _page_mock(body="Qwen chat", usable=True)
    verdict = asyncio.run(_checker(page, raise_auth=True).diagnose_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.EXPIRED.value
    assert verdict.recovery_action is not None


def test_auth_required_from_composer_missing() -> None:
    page = _page_mock(body="Qwen chat", usable=False)
    verdict = asyncio.run(_checker(page).diagnose_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.EXPIRED.value


def test_limited_not_overwritten_by_transient_failure() -> None:
    """A transient probe failure on a LIMITED session must keep it LIMITED."""
    page = _page_mock(body="Qwen chat", usable=True)
    limited_session = _session(status=SessionStatus.LIMITED, reason="QUOTA")
    verdict = asyncio.run(_checker(page, raise_error=ConnectionError).diagnose_session(limited_session))
    assert verdict.status == SessionStatus.LIMITED
    assert verdict.reason == "QUOTA"


def test_unlimited_session_not_marked_limited_on_transient_failure() -> None:
    """A non-LIMITED session that fails the probe is AUTH_REQUIRED, not LIMITED."""
    page = _page_mock(body="Qwen chat", usable=True)
    auth_session = _session(status=SessionStatus.AUTH_REQUIRED)
    verdict = asyncio.run(_checker(page, raise_error=ConnectionError).diagnose_session(auth_session))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason != "QUOTA"


def test_browser_not_configured_returns_auth_required() -> None:
    verdict = asyncio.run(SessionHealthChecker().diagnose_session(_session()))
    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.LAUNCH_FAILURE.value


def test_check_session_still_returns_bool() -> None:
    """check_session (bool protocol method) still works on a clean page."""
    page = _page_mock(body="Qwen chat", usable=True)
    assert asyncio.run(_checker(page).check_session(_session())) is True


def test_check_session_returns_false_on_rate_limit_banner() -> None:
    page = _page_mock(body="You have reached the daily limit.", usable=True)
    assert asyncio.run(_checker(page).check_session(_session())) is False
