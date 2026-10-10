"""Regression tests for the Overview ACTIVE ACCOUNTS tile.

The tile must count usable session accounts (registered profiles that are not
rate-limited), which is a different resource from the per-slot job threads the
Chat Status card tracks. A fresh app run with profiles on disk must report
them, and a limited account must be excluded from the count.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_tui_app import QwenTuiApp
from modules.shared.src.taxonomy_session_vo import (
    SessionInfo,
    SessionPool,
    SessionStatus,
)


def _make_app(session_manager: MagicMock) -> QwenTuiApp:
    return QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        slot_config=MagicMock(),
        setup=MagicMock(),
        session=MagicMock(),
        jobs=MagicMock(),
        session_manager=session_manager,
    )


def _pool(*sessions: SessionInfo) -> SessionPool:
    return SessionPool(sessions=list(sessions))


def _session(name: str, status: SessionStatus) -> SessionInfo:
    return SessionInfo(
        session_id=f"session_{name}",
        name=name,
        path=Path(name),
        status=status,
    )


def _assert_count(pool: SessionPool, expected: int) -> None:
    """Run the app so the workers mix in, then assert the pool-based count."""
    manager = MagicMock()
    manager.load_pool.return_value = pool
    app = _make_app(manager)

    def _check() -> None:
        assert app._active_account_count() == expected

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            _check()

    asyncio.run(_run())


def test_active_account_count_counts_all_usable_profiles() -> None:
    """All registered, non-limited sessions count as active accounts."""
    pool = _pool(
        _session("default", SessionStatus.ACTIVE),
        _session("arwaky007", SessionStatus.UNKNOWN),
    )

    _assert_count(pool, 2)


def test_active_account_count_excludes_limited() -> None:
    """A rate-limited account is not a usable active account."""
    pool = _pool(
        _session("default", SessionStatus.ACTIVE),
        _session("limited", SessionStatus.LIMITED),
        _session("arwaky007", SessionStatus.ACTIVE),
    )

    _assert_count(pool, 2)


def test_active_account_count_without_manager_is_zero() -> None:
    """No session manager in the container means no accounts to report."""
    app = _make_app(None)

    assert app._active_account_count() == 0


def test_flush_metrics_writes_active_account_count() -> None:
    """The Overview ACTIVE ACCOUNTS tile renders the pool-based count."""
    pool = _pool(
        _session("default", SessionStatus.ACTIVE),
        _session("arwaky007", SessionStatus.UNKNOWN),
    )
    manager = MagicMock()
    manager.load_pool.return_value = pool
    app = _make_app(manager)

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            # Slot stats stay untouched: the tile must not borrow the slot
            # counter the way it used to.
            app._slot_stats[1]["status"] = "RUNNING"
            app._flush_metrics()
            from textual.widgets import Label

            assert str(app.query_one("#metric-active", Label).render()) == "2"
            # The Chat card still tracks slots: 1 running out of 10.
            assert str(app.query_one("#metric-threads-ring", Label).render()) == "1/10"

    asyncio.run(_run())
