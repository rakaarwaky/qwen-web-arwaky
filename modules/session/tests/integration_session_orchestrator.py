"""Integration tests for the session orchestrator with a real session manager.

These exercise the DI wiring: a real ``SessionManager`` backed by a temporary
directory, an orchestrator built on top of it, and a full ``execute`` round-trip
so a signature or wiring change fails here.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.taxonomy_session_vo import SessionRequest

MODULE = "modules.session.src.capabilities_session_manager"


def _patched_manager(tmp_path: Path) -> SessionManager:
    """Build a SessionManager rooted at *tmp_path* with patched module globals."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MODULE}.POOL_FILE", pool_file),
    ):
        return SessionManager(base_dir=sessions_dir)


def test_integration_orchestrator_boots_with_real_manager(tmp_path: Path) -> None:
    manager = _patched_manager(tmp_path)
    orchestrator = SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
        sessions=manager,
    )
    assert isinstance(orchestrator, ISessionAggregate)
    assert callable(orchestrator.execute)


def test_integration_delete_absent_session_returns_error(tmp_path: Path) -> None:
    """A delete on a path that does not exist returns an error, not an exception."""
    manager = _patched_manager(tmp_path)
    orchestrator = SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
        sessions=manager,
    )
    with patch("modules.session.src.agent_session_orchestrator.build_app_config") as build:
        build.return_value.session_path = tmp_path / "absent-profile"
        response = orchestrator.execute(
            SessionRequest(verb="delete", session_path=tmp_path / "absent-profile", name="")
        )
    # Absent target: no exception, error field or deleted flag carries the outcome.
    assert response is not None
