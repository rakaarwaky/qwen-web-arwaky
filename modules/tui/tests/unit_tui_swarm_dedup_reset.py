"""Regression tests for FE-2-01: swarm log-dedup caches reset between runs.

``_render_swarm_snapshot`` lazily creates ``_swarm_agent_states`` /
``_swarm_aggregate`` and never clears them. A second swarm run over the
same role set started with the previous run's terminal states cached, so
unchanged agents emitted no log line and the aggregate was suppressed.

The worker must reset both caches at the start of every run. These tests
drive ``_swarm_worker`` itself so removing the reset lines fails them.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from modules.shared.src.swarm.taxonomy_swarm_vo import (
    SwarmAgentSnapshot,
    SwarmSnapshot,
)
from modules.tui.src.surface_tui_app_screen import QwenTuiApp
from modules.tui.tests.fixture_tui_app import make_app


def _snapshot(status: str = "completed") -> SwarmSnapshot:
    return SwarmSnapshot(
        swarm_id="swarm-1",
        input_path=Path("/tmp/in"),
        root_path=Path("/tmp/root"),
        status=status,
        max_attempts=3,
        browser_concurrency=2,
        agents=(
            SwarmAgentSnapshot(agent_id="agent-1", status="completed", attempt=1),
            SwarmAgentSnapshot(agent_id="agent-2", status="completed", attempt=1),
        ),
    )


class _StubSwarm:
    """ISwarmAggregate stand-in that returns a completed snapshot every call."""

    resource_warning: str | None = None

    def execute(self, request: Any) -> Any:
        return MagicMock(snapshot=_snapshot("completed"))


def _wire_sync_cft(app: QwenTuiApp) -> None:
    def _cft(callback: Any, *args: Any, **kwargs: Any) -> None:
        callback(*args, **kwargs)
        return None

    app.call_from_thread = _cft


async def _run_swarm_worker_once(app: QwenTuiApp) -> list[str]:
    """Drive one full ``_swarm_worker`` cycle and return captured swarm lines."""
    from textual.worker import WorkerFailed

    lines: list[str] = []
    app._log_swarm_msg = lambda msg: lines.append(str(msg))
    _wire_sync_cft(app)
    worker = app._swarm_worker(Path("/tmp/in"))
    with contextlib.suppress(WorkerFailed):
        if worker is not None:
            await worker.wait()
    return lines


class TestSwarmDedupReset:
    """A second sequential worker run over the same roles must emit again."""

    def test_second_swarm_worker_run_emits_again_without_manual_clear(self) -> None:
        app = make_app()
        app._swarm = _StubSwarm()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                first = await _run_swarm_worker_once(app)
                assert any("agent-1" in ln for ln in first), first
                assert any("agent-2" in ln for ln in first), first
                assert any("SWARM:" in ln for ln in first), first

                # Second run over the same role set. No manual cache clearing:
                # only the resets inside ``_swarm_worker`` make this emit.
                second = await _run_swarm_worker_once(app)
                assert any("agent-1" in ln for ln in second), second
                assert any("agent-2" in ln for ln in second), second
                assert any("SWARM:" in ln for ln in second), second

        import asyncio

        asyncio.run(_run())

    def test_without_worker_reset_second_render_is_silent(self) -> None:
        """Documents the pre-fix failure mode the worker reset eliminates."""
        app = make_app()
        lines: list[str] = []
        app._log_swarm_msg = lambda msg: lines.append(str(msg))

        snap = _snapshot()
        app._swarm_agent_states = {}
        app._swarm_aggregate = None
        app._render_swarm_snapshot(snap)
        lines.clear()
        # No reset: identical snapshot produces no new lines (the bug).
        app._render_swarm_snapshot(snap)
        assert lines == [], lines

    def test_worker_reset_lines_exist_before_try(self) -> None:
        """Pin placement: resets precede the try so a mid-run failure still clears."""
        import inspect

        from modules.tui.src.surface_tui_workers_store import _TuiWorkersMixin

        source = inspect.getsource(_TuiWorkersMixin._swarm_worker)
        try_idx = source.find("try:")
        reset_agent = source.find("self._swarm_agent_states = {}")
        reset_agg = source.find("self._swarm_aggregate = None")
        assert reset_agent != -1, "worker must reset _swarm_agent_states"
        assert reset_agg != -1, "worker must reset _swarm_aggregate"
        assert 0 < reset_agent < try_idx, source
        assert 0 < reset_agg < try_idx, source

    def test_app_init_declares_empty_caches(self) -> None:
        app = make_app()
        assert app._swarm_agent_states == {}
        assert app._swarm_aggregate is None


__all__ = ["TestSwarmDedupReset"]
