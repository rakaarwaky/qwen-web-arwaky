"""Benchmark for session pool rotation.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. Rotation runs against a stub session manager and a
stub health checker, so the benchmark needs no browser build, no network,
and no saved session.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionStatus

pytestmark = pytest.mark.benchmark


async def _healthy(_session: SessionInfo) -> bool:
    """Report the stub session as healthy."""
    return True


def _adapter() -> SessionRotationAdapter:
    """Return a rotation adapter over a stub pool holding one session."""
    session = SessionInfo(
        session_id="bench-00",
        name="session-0",
        path=Path("/tmp/session-0"),
        status=SessionStatus.ACTIVE,
        created_at=datetime(2026, 1, 1),
    )
    manager = MagicMock()
    manager.load_pool.return_value.get_next_session.return_value = session
    manager.mark_healthy.return_value = None
    checker = MagicMock()
    checker.check_session = _healthy
    return SessionRotationAdapter(manager, checker)


def bench_get_next_session(iterations: int = 1000) -> float:
    """Benchmark one rotation over a healthy stub pool."""
    adapter = _adapter()

    async def _loop() -> None:
        for _ in range(iterations):
            await adapter.get_next_session()

    start = time.perf_counter()
    asyncio.run(_loop())
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_get_next_session() -> None:
    """Report benchmark results for one pool rotation."""
    micros = bench_get_next_session()
    print(f"\n[BENCHMARK] session get_next_session: {micros:.2f} µs/call")
    assert micros > 0
