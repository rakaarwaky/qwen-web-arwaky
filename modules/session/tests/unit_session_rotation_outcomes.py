"""Unit tests for rotation no_eligible_session outcomes (BA-2-002).

Pins the locked decisions:
- Fail fast, explicit outcome when no eligible session remains.
- Never submit through a known-LIMITED profile.
- outcome/reason fields in the rotation response contract.
- No promise that quota resets; no invented reset time.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_rotation_adapter import (
    AllSessionsLimitedError,
    SessionRotationAdapter,
)
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    SessionHealthResult,
    SessionInfo,
    SessionPool,
    SessionStatus,
)


def _session(index: int, status: SessionStatus = SessionStatus.AUTH_REQUIRED) -> SessionInfo:
    return SessionInfo(
        session_id=f"rot-{index}",
        name=f"session-{index}",
        path=Path(f"/tmp/rot-{index}"),
        status=status,
        created_at=datetime(2026, 1, 1),
    )


def _verdict(session: SessionInfo) -> SessionHealthResult:
    if session.status == SessionStatus.ACTIVE:
        return SessionHealthResult(session_id=session.session_id, status=SessionStatus.ACTIVE)
    elif session.status == SessionStatus.LIMITED:
        return SessionHealthResult(
            session_id=session.session_id,
            status=SessionStatus.LIMITED,
            reason="QUOTA",
            evidence="Daily limit reached",
        )
    return SessionHealthResult(
        session_id=session.session_id,
        status=SessionStatus.AUTH_REQUIRED,
        reason="EXPIRED",
        evidence="Session expired",
    )


def _adapter(pool: SessionPool, exclude_ids: tuple[str, ...] = ()) -> tuple[SessionRotationAdapter, list[SessionInfo]]:
    manager = MagicMock()
    manager.load_pool.return_value = pool
    manager.mark_healthy = MagicMock()
    manager.mark_limited = MagicMock()
    manager.mark_auth_required = MagicMock()
    checker = MagicMock()

    async def _diagnose(session: SessionInfo) -> SessionHealthResult:
        return _verdict(session)

    checker.diagnose_session = _diagnose
    adapter = SessionRotationAdapter(manager, checker)
    return adapter, []


def test_empty_pool_returns_no_eligible_session() -> None:
    pool = SessionPool.empty()
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest()))
    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "empty_pool"
    assert resp.recovery_action is not None


def test_single_limited_pool_returns_no_eligible_session() -> None:
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED),))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest()))
    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "all_sessions_limited"


def test_all_limited_pool_returns_no_eligible_session() -> None:
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED), _session(1, SessionStatus.LIMITED)))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest()))
    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "all_sessions_limited"


def test_excluded_all_pool_returns_no_eligible_session() -> None:
    pool = SessionPool(sessions=(_session(0, SessionStatus.ACTIVE), _session(1, SessionStatus.ACTIVE)))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=("rot-0", "rot-1"))))
    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "all_sessions_excluded"


def test_mixed_pool_returns_next_healthy_session() -> None:
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED), _session(1, SessionStatus.ACTIVE)))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest()))
    assert resp.session is not None
    assert resp.session.session_id == "rot-1"
    assert resp.outcome == "success"
    assert resp.reason is None


def test_excluded_limited_session_skipped_to_next() -> None:
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED), _session(1, SessionStatus.ACTIVE)))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=("rot-0",))))
    assert resp.session is not None
    assert resp.session.session_id == "rot-1"


def test_known_limited_session_never_selected() -> None:
    """Never submits through a known-LIMITED profile."""
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED),))
    adapter, _ = _adapter(pool)
    resp = asyncio.run(adapter.rotate(RotatorRequest()))
    assert resp.session is None
    assert resp.outcome == "no_eligible_session"


def test_execute_with_rotation_returns_error_not_raise_on_exhausted_pool() -> None:
    """execute_with_rotation no longer raises AllSessionsLimitedError; returns an explicit outcome."""
    pool = SessionPool(sessions=(_session(0, SessionStatus.LIMITED),))
    adapter, _ = _adapter(pool)
    result, session = asyncio.run(adapter.execute_with_rotation("hello"))
    assert session is None
    assert "no_eligible_session" in result


def test_all_sessions_limited_error_still_importable() -> None:
    """AllSessionsLimitedError is kept as a deprecated alias for import compatibility."""
    err = AllSessionsLimitedError(pool=SessionPool.empty())
    assert isinstance(err, Exception)
    assert "rate-limited" in str(err)
