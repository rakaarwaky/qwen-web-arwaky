"""End-to-end tests for the session aggregate and its rotation companion.

The session door validates and deletes; the rotation seam picks the next
session a run should use. These drive both over stub browser and pool
seams, so no browser build, no network, and no saved session are needed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionPool, SessionRequest, SessionStatus


def _session() -> SessionInfo:
    return SessionInfo(
        session_id="e2e-0",
        name="session-0",
        path=Path("/tmp/session-0"),
        status=SessionStatus.ACTIVE,
        created_at=datetime(2026, 1, 1),
    )


def _orchestrator() -> tuple[SessionOrchestrator, MagicMock]:
    """Return a session orchestrator over stub browser and observability seams."""
    browser = MagicMock()
    observability = MagicMock()
    sessions = MagicMock()
    return SessionOrchestrator(browser=browser, observability=observability, sessions=sessions), browser


def _rotation_adapter() -> SessionRotationAdapter:
    async def _healthy(_session: SessionInfo) -> bool:
        return True

    manager = MagicMock()
    manager.load_pool.return_value = SessionPool(sessions=[_session()])
    manager.mark_healthy.return_value = None
    checker = MagicMock()
    checker.check_session = _healthy
    return SessionRotationAdapter(manager, checker)


def test_e2e_the_aggregate_validates_a_session_through_the_browser_seam(tmp_path: Path) -> None:
    orchestrator, browser = _orchestrator()
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    browser.check_session.assert_called_once()


def test_e2e_a_healthy_browser_seam_reports_the_session_valid(tmp_path: Path) -> None:
    orchestrator, browser = _orchestrator()
    browser.check_session.return_value = True
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    response = orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    assert response.valid is True


def test_e2e_an_unhealthy_browser_seam_reports_the_session_invalid(tmp_path: Path) -> None:
    """A session that no longer authenticates is reported invalid rather
    than repaired, so the operator chooses to re-login."""
    orchestrator, browser = _orchestrator()
    browser.check_session.return_value = False
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    response = orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    assert response.valid is False


def test_e2e_a_rotation_returns_a_usable_session() -> None:
    chosen = asyncio.run(_rotation_adapter().get_next_session())

    assert chosen is not None
    assert chosen.session_id == "e2e-0"
