"""Unit tests for the config health-probe capability.

``ConfigHealthProbe`` composes the functional smoke gate the update pipeline
runs as its postflight verification step (FR-UPDATE-003, issue #294 / #506).
Pinned here against the capability's public seam: the gate it returns yields
the non-interactive doctor checks as ``(name, passed, detail)`` triples, and
the session aggregate is a required positional argument so a wiring gap
cannot masquerade as an empty pool.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.cli.src.surface_cli_doctor_command import run_doctor_checks
from modules.config.src.capabilities_config_health_probe import ConfigHealthProbe
from modules.shared.src.config.contract_config_protocol import IConfigHealthProbeProtocol
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse


def _healthy_pool_aggregate() -> MagicMock:
    """Test-side aggregate with one healthy session in the pool."""
    session = MagicMock()
    session.session_id = "abc"
    session.name = "default"
    session.is_healthy = True
    session.is_limited = False
    session.is_auth_required = False
    session.status.value = "healthy"
    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(
        sessions=SessionList([session]),
        message="1 session(s)",
    )
    return aggregate


def test_probe_implements_the_health_probe_protocol() -> None:
    """The capability implements the config health-probe contract."""
    assert IConfigHealthProbeProtocol in ConfigHealthProbe.__mro__


def test_gate_yields_name_passed_detail_triples() -> None:
    """The gate yields one triple per non-interactive doctor check."""
    gate = ConfigHealthProbe().build_gate(_healthy_pool_aggregate(), run_doctor_checks)
    results = gate()
    assert results
    for name, passed, detail in results:
        assert isinstance(name, str)
        assert isinstance(passed, bool)
        assert isinstance(detail, str)
    names = {name for name, _, _ in results}
    assert "Session Authentication Token" in names
    assert "Browser Smoke Test" not in names


def test_gate_requires_a_session_aggregate() -> None:
    """The session aggregate is a required positional argument — no default."""
    with pytest.raises(TypeError, match="session"):
        ConfigHealthProbe().build_gate(run_checks=run_doctor_checks)  # type: ignore[call-arg]
