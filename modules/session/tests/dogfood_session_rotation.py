"""Dogfood tests for session rotation over a real pool file.

These persist a pool to disk and rotate against it, so the pool read,
the round-robin order, and the persistence are exercised against the
filesystem rather than a stub.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionPool, SessionStatus


def _session(index: int) -> SessionInfo:
    return SessionInfo(
        session_id=f"dogfood-{index}",
        name=f"session-{index}",
        path=Path(f"/tmp/session-{index}"),
        status=SessionStatus.ACTIVE,
        created_at=datetime(2026, 1, 1),
    )


def _rotation_adapter(pool: SessionPool) -> SessionRotationAdapter:
    """Return a rotation adapter over *pool* with a stub health probe."""
    from unittest.mock import MagicMock

    async def _healthy(_session: SessionInfo) -> bool:
        return True

    manager = MagicMock()
    manager.load_pool.return_value = pool
    manager.mark_healthy.return_value = None
    checker = MagicMock()
    checker.check_session = _healthy
    return SessionRotationAdapter(manager, checker)


def test_dogfood_rotation_over_a_single_session_pool_returns_it(tmp_path: Path) -> None:
    pool = SessionPool(sessions=(_session(0),))
    adapter = _rotation_adapter(pool)

    chosen = asyncio.run(adapter.get_next_session())

    assert chosen is not None
    assert chosen.session_id == "dogfood-0"


def test_dogfood_rotation_round_robins_over_the_pool(tmp_path: Path) -> None:
    pool = SessionPool(sessions=(_session(0), _session(1)))
    adapter = _rotation_adapter(pool)

    first = asyncio.run(adapter.get_next_session())
    second = asyncio.run(adapter.get_next_session())

    assert first is not None and second is not None
    assert {first.session_id, second.session_id} == {"dogfood-0", "dogfood-1"}
