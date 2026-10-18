"""Unit tests for the rotation exhaustion contract (SESSION-02, D2).

When every pooled session is rate-limited, ``rotate`` returns
``RotatorResponse(session=None, throttled=True)`` — exhaustion is a state
to report, not a fault — while ``execute_with_rotation`` still raises
``AllSessionsLimitedError``. Rotation also iterates deterministically
from ``pool.current_index`` and probes each session exactly once.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.session.src.capabilities_session_rotation_adapter import (
    AllSessionsLimitedError,
    SessionRotationAdapter,
)
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
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

    async def check_session(self, session: SessionInfo) -> bool:
        self.probed.append(session.session_id)
        return session.session_id in self.healthy_ids


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


def test_execute_with_rotation_raises_when_all_limited(tmp_path: Path) -> None:
    """``execute_with_rotation`` keeps raising on exhaustion (D2)."""
    pool = _pool([SessionStatus.LIMITED, SessionStatus.LIMITED], tmp_path)
    checker = _StubChecker(healthy_ids=set())
    adapter = _adapter(pool, checker)

    with pytest.raises(AllSessionsLimitedError):
        asyncio.run(adapter.execute_with_rotation("prompt"))
    assert adapter.metrics.sessions_exhausted == 1
