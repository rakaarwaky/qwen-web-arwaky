"""Unit tests for SessionRotationAdapter: rotation outcomes and exhaustion.

Covers the locked decisions (SESSION-02, BA-2-002):
- ``rotate`` returns an explicit ``no_eligible_session`` outcome (with
  reason and recovery action) when no eligible session remains, and the
  derived ``throttled`` view reads True on that outcome.
- ``execute_with_rotation`` returns an explicit error outcome on
  exhaustion (never raises); ``AllSessionsLimitedError`` is a deprecated
  alias kept for import compatibility.
- Rotation iterates deterministically from ``pool.current_index`` and
  probes each session exactly once; exclusions are honored.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    SessionHealthResult,
    SessionInfo,
    SessionPool,
    SessionStatus,
)


def _info(name: str, path: Path, status: SessionStatus = SessionStatus.ACTIVE) -> SessionInfo:
    return SessionInfo(session_id=name, name=name, path=path, status=status)


def _pool(statuses: list[SessionStatus], tmp_path: Path) -> SessionPool:
    return SessionPool(
        sessions=[_info(f"session_{i + 1}", tmp_path / f"p{i + 1}", status) for i, status in enumerate(statuses)],
        current_index=0,
    )


class _StubChecker:
    """Health checker stub that counts probes and returns a fixed verdict."""

    def __init__(self, healthy_ids: set[str]) -> None:
        self.healthy_ids = healthy_ids
        self.probed: list[str] = []

    def _verdict(self, session: SessionInfo) -> SessionHealthResult:
        if session.session_id in self.healthy_ids:
            return SessionHealthResult(session_id=session.session_id, status=SessionStatus.ACTIVE)
        status = session.status
        if status == SessionStatus.LIMITED:
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

    async def check_session(self, session: SessionInfo) -> bool:
        self.probed.append(session.session_id)
        return session.session_id in self.healthy_ids

    async def diagnose_session(self, session: SessionInfo) -> SessionHealthResult:
        self.probed.append(session.session_id)
        return self._verdict(session)

    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        return pool

    def check_pool_sync(self, pool: SessionPool, session_manager) -> list[tuple[SessionInfo, SessionHealthResult]]:
        return [(s, self._verdict(s)) for s in pool.sessions]

    def summarize_pool_results(self, results: list[tuple[SessionInfo, SessionHealthResult]]) -> tuple[int, int]:
        return (sum(1 for _, v in results if v.is_healthy), len(results))


def _adapter(pool: SessionPool, checker: _StubChecker) -> SessionRotationAdapter:
    manager = MagicMock()
    manager.load_pool.return_value = pool
    return SessionRotationAdapter(manager, checker)


def test_rotation_all_sessions_limited_reports_throttle(tmp_path: Path) -> None:
    """An all-limited pool reports ``session=None, throttled=True`` (D2)."""
    pool = _pool([SessionStatus.LIMITED, SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    response = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=())))

    assert response.session is None
    assert response.throttled is True
    assert response.error is None
    assert adapter.metrics.sessions_exhausted == 1
    assert adapter.metrics.successful_rotations == 0
    assert len(checker.probed) == 2


def test_rotation_selects_the_first_healthy_session(tmp_path: Path) -> None:
    """A healthy candidate wins and is reported as not throttled."""
    pool = _pool([SessionStatus.LIMITED, SessionStatus.ACTIVE], tmp_path)
    checker = _StubChecker(healthy_ids={"session_2"})
    adapter = _adapter(pool, checker)

    response = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=())))

    assert response.session is not None
    assert response.session.session_id == "session_2"
    assert response.throttled is False


def test_rotation_skips_excluded_ids(tmp_path: Path) -> None:
    """Sessions a caller already tried are skipped, not re-probed."""
    pool = _pool([SessionStatus.ACTIVE, SessionStatus.ACTIVE], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    response = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=("session_1",))))

    assert response.session is None
    assert response.throttled is True
    assert "session_1" not in checker.probed


def test_rotation_is_deterministic_from_current_index(tmp_path: Path) -> None:
    """The same pool state resolves the same candidate, starting at current_index."""
    pool = _pool([SessionStatus.UNKNOWN, SessionStatus.UNKNOWN, SessionStatus.UNKNOWN], tmp_path)
    pool.current_index = 2
    checker = _StubChecker(healthy_ids={"session_1"})
    adapter = _adapter(pool, checker)

    first = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=())))
    pool.current_index = 2
    checker.probed.clear()
    second = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=())))

    assert first.session is not None and second.session is not None
    assert first.session.session_id == second.session.session_id
    # Iteration started at index 2, so session_3 is probed first.
    assert checker.probed[0] == "session_3"


def test_get_next_session_probes_each_session_once_when_all_limited(tmp_path: Path) -> None:
    """An all-limited pool of N sessions costs exactly N probes (BE-4-002)."""
    pool = _pool([SessionStatus.LIMITED] * 3, tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    assert asyncio.run(adapter.get_next_session()) is None
    assert len(checker.probed) == 3
    assert len(set(checker.probed)) == 3


def test_get_next_session_skips_the_round_robin_candidate_in_the_fallback(tmp_path: Path) -> None:
    """The fallback pass must not re-probe the round-robin candidate."""
    pool = _pool([SessionStatus.LIMITED, SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    assert asyncio.run(adapter.get_next_session()) is None
    assert sorted(checker.probed) == ["session_1", "session_2"]


def test_execute_with_rotation_reports_outcome_on_exhausted_pool(tmp_path: Path) -> None:
    """``execute_with_rotation`` returns an explicit error outcome on exhaustion, never submits."""
    pool = _pool([SessionStatus.LIMITED, SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    result, session = asyncio.run(adapter.execute_with_rotation("prompt"))

    assert session is None
    assert "no_eligible_session" in result
    assert adapter.metrics.sessions_exhausted == 1


def test_all_sessions_limited_error_still_importable() -> None:
    """``AllSessionsLimitedError`` is kept as a deprecated alias for import compatibility."""
    from modules.session.src.capabilities_session_rotation_adapter import AllSessionsLimitedError

    err = AllSessionsLimitedError(pool=SessionPool.empty())
    assert isinstance(err, Exception)
    assert "rate-limited" in str(err)


# ── outcome/reason contract (BA-2-002, merged from unit_session_rotation_outcomes) ─


def test_rotation_empty_pool_returns_empty_pool_reason(tmp_path: Path) -> None:
    pool = _pool([], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    resp = asyncio.run(adapter.rotate(RotatorRequest()))

    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "empty_pool"
    assert resp.recovery_action is not None


def test_rotation_single_limited_pool_returns_all_sessions_limited(tmp_path: Path) -> None:
    pool = _pool([SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    resp = asyncio.run(adapter.rotate(RotatorRequest()))

    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "all_sessions_limited"


def test_rotation_all_excluded_returns_all_sessions_excluded(tmp_path: Path) -> None:
    pool = _pool([SessionStatus.ACTIVE, SessionStatus.ACTIVE], tmp_path)
    checker = _StubChecker(healthy_ids={"session_1", "session_2"})
    adapter = _adapter(pool, checker)

    resp = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=("session_1", "session_2"))))

    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
    assert resp.reason == "all_sessions_excluded"


def test_rotation_mixed_pool_selects_next_healthy(tmp_path: Path) -> None:
    pool = _pool([SessionStatus.LIMITED, SessionStatus.ACTIVE], tmp_path)
    checker = _StubChecker(healthy_ids={"session_2"})
    adapter = _adapter(pool, checker)

    resp = asyncio.run(adapter.rotate(RotatorRequest()))

    assert resp.session is not None
    assert resp.session.session_id == "session_2"
    assert resp.outcome == "success"
    assert resp.reason is None


def test_rotation_known_limited_session_never_selected(tmp_path: Path) -> None:
    """Never submits through a known-LIMITED profile."""
    pool = _pool([SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    resp = asyncio.run(adapter.rotate(RotatorRequest(exclude_ids=())))

    assert resp.session is None
    assert resp.outcome == "no_eligible_session"
