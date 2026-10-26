"""Unit tests for the session renewal capability.

Mocks the browser seam so no real Chromium launch happens. Covers the three
required scenarios:

1. healthy session skips renewal entirely,
2. expired auth + valid refresh → renewed, returns healthy,
3. expired auth + expired/missing refresh → raises AuthRequiredError.

Also exercises the cookie-probe utility functions on a real (tmp) SQLite
cookie store.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.session.src.capabilities_session_renewal import SessionRenewer
from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserLifecycleProtocol,
    IBrowserNavigationProtocol,
)
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.utility_session_renewal_cookie_probe import (
    is_auth_session_expired,
    is_refresh_token_valid,
    renewal_is_possible,
)

# Chromium cookie epoch: microseconds since 1601-01-01.
_CHROMIUM_EPOCH_OFFSET_US = 11_644_473_600_000_000


def _cookie_ts_us(expires_at_utc: datetime) -> int:
    """Convert a UTC datetime to Chromium's ``expires_utc`` microseconds."""
    return int(expires_at_utc.timestamp() * 1_000_000) + _CHROMIUM_EPOCH_OFFSET_US


def _make_cookie_db(profile_dir: Path, *, auth_future: bool, refresh_future: bool) -> Path:
    """Create a real SQLite cookie store under *profile_dir* and return its path."""
    cookie_dir = profile_dir / "Default"
    cookie_dir.mkdir(parents=True, exist_ok=True)
    db_path = cookie_dir / "Cookies"
    db_path.write_bytes(b"")
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL DEFAULT 0,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            encrypted_value BLOB NOT NULL DEFAULT X'00',
            path TEXT NOT NULL DEFAULT '/',
            expires_utc INTEGER NOT NULL DEFAULT 0,
            is_secure INTEGER NOT NULL DEFAULT 0,
            is_httponly INTEGER NOT NULL DEFAULT 0,
            last_access_utc INTEGER NOT NULL DEFAULT 0,
            has_expires INTEGER NOT NULL DEFAULT 0,
            is_persistent INTEGER NOT NULL DEFAULT 0,
            priority INTEGER NOT NULL DEFAULT 0,
            samesite INTEGER NOT NULL DEFAULT 0,
            source_scheme INTEGER NOT NULL DEFAULT 0,
            source_port INTEGER NOT NULL DEFAULT 0,
            last_update_utc INTEGER NOT NULL DEFAULT 0,
            source_type INTEGER NOT NULL DEFAULT 0,
            has_cross_site_ancestor INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    now = datetime.now(timezone.utc)
    auth_expiry = _cookie_ts_us(now) + (86_400_000_000 if auth_future else -86_400_000_000)
    refresh_expiry = _cookie_ts_us(now) + (30 * 86_400_000_000 if refresh_future else -86_400_000_000)
    conn.execute(
        "INSERT INTO cookies (host_key, name, expires_utc, has_expires, is_persistent) VALUES (?, ?, ?, 1, 1)",
        ("auth.qwen.ai", "auth-session", auth_expiry),
    )
    conn.execute(
        "INSERT INTO cookies (host_key, name, expires_utc, has_expires, is_persistent) VALUES (?, ?, ?, 1, 1)",
        (".qwen.ai", "refresh_token", refresh_expiry),
    )
    conn.commit()
    conn.close()
    return db_path


# ── Cookie probe utility tests ──────────────────────────────────────────────


def test_healthy_session_reports_auth_not_expired(tmp_path: Path) -> None:
    _make_cookie_db(tmp_path, auth_future=True, refresh_future=True)
    assert is_auth_session_expired(tmp_path) is False
    assert is_refresh_token_valid(tmp_path) is True
    # Both live: renewal is not even needed.
    assert renewal_is_possible(tmp_path) is False


def test_expired_auth_with_valid_refresh_is_renewable(tmp_path: Path) -> None:
    _make_cookie_db(tmp_path, auth_future=False, refresh_future=True)
    assert is_auth_session_expired(tmp_path) is True
    assert is_refresh_token_valid(tmp_path) is True
    assert renewal_is_possible(tmp_path) is True


def test_expired_auth_and_expired_refresh_is_not_renewable(tmp_path: Path) -> None:
    _make_cookie_db(tmp_path, auth_future=False, refresh_future=False)
    assert is_auth_session_expired(tmp_path) is True
    assert is_refresh_token_valid(tmp_path) is False
    assert renewal_is_possible(tmp_path) is False


def test_missing_profile_reports_expired_and_not_renewable(tmp_path: Path) -> None:
    assert is_auth_session_expired(tmp_path / "absent") is True
    assert is_refresh_token_valid(tmp_path / "absent") is False
    assert renewal_is_possible(tmp_path / "absent") is False


# ── SessionRenewer tests ────────────────────────────────────────────────────


def _renewer(tmp_path: Path) -> tuple[SessionRenewer, MagicMock]:
    browser: MagicMock = MagicMock(spec=IBrowserLifecycleProtocol)
    observability: MagicMock = MagicMock()
    observability.get_logger.return_value = MagicMock()
    renewer = SessionRenewer(browser, observability)
    return renewer, browser


def _cfg(profile_dir: Path) -> AppConfig:
    return AppConfig(
        input_path=profile_dir,
        output_path=profile_dir,
        session_path=profile_dir,
    )


def test_healthy_session_skips_renewal(tmp_path: Path) -> None:
    """A live auth-session cookie means no browser work is needed."""
    _make_cookie_db(tmp_path, auth_future=True, refresh_future=True)
    renewer, browser = _renewer(tmp_path)
    assert renewer.renew_session_if_stale(_cfg(tmp_path)) is True
    browser.renew_session.assert_not_called()


def test_expired_auth_with_valid_refresh_renews(tmp_path: Path) -> None:
    """Stale auth + live refresh: the browser warm-up runs and succeeds."""
    _make_cookie_db(tmp_path, auth_future=False, refresh_future=True)
    renewer, browser = _renewer(tmp_path)
    browser.renew_session.return_value = None
    assert renewer.renew_session_if_stale(_cfg(tmp_path)) is True
    browser.renew_session.assert_called_once()
    # The renewed event path completes without raising.
    args, _ = browser.renew_session.call_args
    assert args[0].session_path == tmp_path


def test_expired_auth_with_expired_refresh_raises_auth_required(tmp_path: Path) -> None:
    """Both cookies dead: no browser attempt, straight to the login fallback."""
    _make_cookie_db(tmp_path, auth_future=False, refresh_future=False)
    renewer, browser = _renewer(tmp_path)
    with pytest.raises(AuthRequiredError) as excinfo:
        renewer.renew_session_if_stale(_cfg(tmp_path))
    assert excinfo.value.session_expired is True
    browser.renew_session.assert_not_called()


def test_browser_renewal_failure_raises_auth_required(tmp_path: Path) -> None:
    """The refresh token looks live but the warm-up still fails (e.g. the
    site rejected it): the operator must be told to log in manually."""
    _make_cookie_db(tmp_path, auth_future=False, refresh_future=True)
    renewer, browser = _renewer(tmp_path)
    browser.renew_session.side_effect = RuntimeError("page landed on login view")
    with pytest.raises(AuthRequiredError) as excinfo:
        renewer.renew_session_if_stale(_cfg(tmp_path))
    assert excinfo.value.session_expired is True
    assert "login" in str(excinfo.value).lower()


def test_missing_refresh_cookie_raises_auth_required(tmp_path: Path) -> None:
    """No refresh_token at all is the same verdict as an expired one."""
    cookie_dir = tmp_path / "Default"
    cookie_dir.mkdir(parents=True)
    db = cookie_dir / "Cookies"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE cookies (
            host_key TEXT NOT NULL,
            name TEXT NOT NULL,
            expires_utc INTEGER NOT NULL DEFAULT 0,
            has_expires INTEGER NOT NULL DEFAULT 0,
            is_persistent INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "INSERT INTO cookies (host_key, name, expires_utc, has_expires, is_persistent) VALUES (?, ?, ?, 1, 1)",
        ("auth.qwen.ai", "auth-session", 1),  # expired
    )
    conn.commit()
    conn.close()
    renewer, browser = _renewer(tmp_path)
    with pytest.raises(AuthRequiredError) as excinfo:
        renewer.renew_session_if_stale(_cfg(tmp_path))
    assert excinfo.value.session_expired is True
    browser.renew_session.assert_not_called()


# ── Orchestrator integration: renewal is attempted on validation failure ──


def test_orchestrator_validation_falls_back_to_renewer(tmp_path: Path) -> None:
    """When the browser probe fails, _validate_saved_session consults the
    injected renewer before reporting the session invalid."""
    from modules.session.src.agent_session_orchestrator import SessionOrchestrator

    _make_cookie_db(tmp_path, auth_future=False, refresh_future=True)
    browser = MagicMock(spec=IBrowserLifecycleProtocol)
    # The initial probe must report the session not ready (check_session
    # returns False) so the renewal path runs; the post-renewal re-validation
    # must then pass (check_session returns True) because the renewed
    # auth-session cookie is live again.
    probe_page = MagicMock()
    probe_page.pages = [probe_page]
    probe_page.new_page = MagicMock()
    browser.browser_session.return_value.__enter__ = MagicMock(return_value=probe_page)
    browser.browser_session.return_value.__exit__ = MagicMock(return_value=False)
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()

    renewer = MagicMock()
    renewer.renew_session_if_stale.return_value = True

    orch = SessionOrchestrator(
        browser_lifecycle=browser,
        browser_navigation=MagicMock(spec=IBrowserNavigationProtocol),
        observability=observability,
        renewer=renewer,
    )
    # The initial probe fails (check_session False, no raise), so the
    # orchestrator consults the renewer; the post-renewal re-validation
    # passes because the renewed auth-session cookie is now live.
    with (
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
        patch("modules.session.src.agent_session_orchestrator.check_session", side_effect=[False, True]) as check,
    ):
        build.return_value = _cfg(tmp_path)
        assert orch._validate_saved_session(_cfg(tmp_path)) is True
    check.assert_called()
    renewer.renew_session_if_stale.assert_called_once()


def test_orchestrator_without_renewer_reports_invalid(tmp_path: Path) -> None:
    """No renewer wired in: the legacy behaviour — probe fails, session invalid."""
    from modules.session.src.agent_session_orchestrator import SessionOrchestrator

    _make_cookie_db(tmp_path, auth_future=False, refresh_future=False)
    browser = MagicMock(spec=IBrowserLifecycleProtocol)
    probe_page = MagicMock()
    probe_page.pages = [probe_page]
    browser.browser_session.return_value.__enter__ = MagicMock(return_value=probe_page)
    browser.browser_session.return_value.__exit__ = MagicMock(return_value=False)
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()
    orch = SessionOrchestrator(
        browser_lifecycle=browser,
        browser_navigation=MagicMock(spec=IBrowserNavigationProtocol),
        observability=observability,
    )
    with (
        patch("modules.session.src.agent_session_orchestrator.build_app_config") as build,
        patch("modules.session.src.agent_session_orchestrator.check_session", return_value=False),
    ):
        build.return_value = _cfg(tmp_path)
        assert orch._validate_saved_session(_cfg(tmp_path)) is False
