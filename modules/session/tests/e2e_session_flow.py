"""End-to-end tests for the session aggregate.

The session door validates and deletes over stub browser and observability
seams, so no browser build, no network, and no saved session are needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.shared.src.session.taxonomy_session_vo import SessionRequest


def _orchestrator() -> tuple[SessionOrchestrator, MagicMock]:
    """Return a session orchestrator over stub browser and observability seams."""
    browser = MagicMock()
    observability = MagicMock()
    sessions = MagicMock()
    return SessionOrchestrator(observability=observability, browser=browser, sessions=sessions), browser


def test_e2e_the_aggregate_validates_a_session_through_the_browser_seam(tmp_path: Path) -> None:
    orchestrator, browser = _orchestrator()
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    with patch("modules.session.src.agent_session_orchestrator.check_session") as check:
        orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    check.assert_called_once()


def test_e2e_a_healthy_browser_seam_reports_the_session_valid(tmp_path: Path) -> None:
    orchestrator, browser = _orchestrator()
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    with patch("modules.session.src.agent_session_orchestrator.check_session", return_value=True):
        response = orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    assert response.valid is True


def test_e2e_an_unhealthy_browser_seam_reports_the_session_invalid(tmp_path: Path) -> None:
    """A session that no longer authenticates is reported invalid rather
    than repaired, so the operator chooses to re-login."""
    orchestrator, browser = _orchestrator()
    session_path = tmp_path / "qwen_session"
    session_path.mkdir()

    with patch("modules.session.src.agent_session_orchestrator.check_session", return_value=False):
        response = orchestrator.execute(SessionRequest(verb="validate", session_path=session_path))

    assert response.valid is False
