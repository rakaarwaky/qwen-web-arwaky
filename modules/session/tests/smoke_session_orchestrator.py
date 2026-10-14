"""Smoke tests for the session orchestrator.

The session aggregate is what surfaces call to validate, rotate, or delete
a session, so the smoke path is "boot the orchestrator and confirm the
aggregate door is present and callable".
"""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate


def test_smoke_orchestrator_exposes_the_aggregate_door() -> None:
    orchestrator = SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
    )
    assert isinstance(orchestrator, ISessionAggregate)
    assert callable(orchestrator.execute)


def test_smoke_orchestrator_boots_with_real_manager() -> None:
    from modules.session.src.capabilities_session_manager import SessionManager

    orchestrator = SessionOrchestrator(
        browser=MagicMock(),
        observability=MagicMock(),
        sessions=SessionManager(),
    )
    assert isinstance(orchestrator, ISessionAggregate)
