"""Regression tests: prompt direct must use the pool session even with one member.

``_resolve_session_for_prompt`` selects a pool session for prompt commands
(including a pool of exactly one), and ``_session_resolver`` must hand that
selection to the direct pipeline. The direct pipeline builds its own
AppConfig, so without the resolver the pool choice would be dropped and the
default session used.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from modules.root_cli_main_entry import _resolve_session_for_prompt, _session_resolver
from modules.shared.src.taxonomy_core_constant import DEFAULT_SESSION
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionPool, SessionStatus


def _container_with_single_pool() -> MagicMock:
    pool = SessionPool(
        sessions=(
            SessionInfo(
                session_id="session_1",
                name="session_1",
                path=Path("/home/raka/.qwen-web-arwaky/sessions/session_1"),
                status=SessionStatus.ACTIVE,
                created_at=datetime(2026, 1, 1),
            ),
        ),
    )
    session_manager = MagicMock()
    session_manager.load_pool.return_value = pool
    rotator = MagicMock()
    resp = MagicMock()
    resp.session = pool.sessions[0]
    # ISessionRotatorProtocol.rotate is async; an AsyncMock makes `await`
    # hand back the response instead of raising TypeError (which the
    # resolver's except-Exception would silently swallow).
    rotator.rotate = AsyncMock(return_value=resp)
    return MagicMock(session_manager=session_manager, session_rotator=rotator)


def _prompt_args() -> argparse.Namespace:
    return argparse.Namespace(action="prompt", prompt_command="direct")


def _pool_session_path(container: MagicMock) -> Path:
    return container.session_manager.load_pool.return_value.sessions[0].path


class TestResolveSessionForPrompt:
    def test_single_session_pool_resolves_a_session(self) -> None:
        """A pool of exactly one member must still resolve the profile.

        The selection must not require the pool to be larger than the
        single-session case, so the logged-in profile is used instead of an
        empty default.
        """
        container = _container_with_single_pool()
        args = _prompt_args()

        _resolve_session_for_prompt(args, container)

        assert args._session_override == _pool_session_path(container)
        assert args._session_override != DEFAULT_SESSION


class TestSessionResolver:
    def test_single_session_pool_yields_the_pool_session(self) -> None:
        container = _container_with_single_pool()
        args = _prompt_args()

        _resolve_session_for_prompt(args, container)
        resolver = _session_resolver(args)

        assert resolver() == _pool_session_path(container)
        assert resolver() != DEFAULT_SESSION

    def test_resolver_falls_back_to_none_for_an_empty_pool(self) -> None:
        """An empty pool has no session, so the resolver reports no override."""
        empty = MagicMock()
        empty.load_pool.return_value = SessionPool.empty()
        container = MagicMock(session_manager=empty)
        args = _prompt_args()

        _resolve_session_for_prompt(args, container)
        resolver = _session_resolver(args)

        assert resolver() is None

    def test_resolver_returns_none_for_a_non_prompt_command(self) -> None:
        args = argparse.Namespace(action="doctor")

        resolver = _session_resolver(args)

        assert resolver() is None
