"""Unit tests for the config health probe capability.

The probe is the post-update functional gate Root injects as ``ISmokeGate``
(issue #294 / #506): ``build_smoke_gate`` must yield ``(name, passed, detail)``
triples at call time, thread the injected session aggregate through the pool
check, and refuse to build without an aggregate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.config.src.capabilities_config_health_probe import (
    ConfigHealthProbe,
    build_smoke_gate,
)
from modules.shared.src.config.taxonomy_config_vo import HealthProbeRecord
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse
from modules.shared.src.update.contract_update_protocol import ISmokeGate


def _pool_aggregate(*, with_healthy_session: bool = False) -> MagicMock:
    """Test-side aggregate answering the list verb from a synthetic pool."""
    aggregate = MagicMock()
    if with_healthy_session:
        session = MagicMock()
        session.session_id = "abc"
        session.name = "default"
        session.is_healthy = True
        session.is_limited = False
        session.status.value = "healthy"
        aggregate.execute.return_value = SessionResponse(sessions=SessionList([session]), message="1 session(s)")
    else:
        aggregate.execute.return_value = SessionResponse(sessions=SessionList([]), message="0 sessions")
    return aggregate


# ─── build_smoke_gate ─────────────────────────────────────────────────────


def test_build_smoke_gate_returns_the_is_smoke_gate_callable() -> None:
    """The factory's return is the ISmokeGate signature the updater types."""
    gate: ISmokeGate = build_smoke_gate(_pool_aggregate())
    results = gate()
    assert results
    for name, passed, detail in results:
        assert isinstance(name, str)
        assert isinstance(passed, bool)
        assert isinstance(detail, str)


def test_build_smoke_gate_requires_a_session_aggregate() -> None:
    """No default aggregate: a wiring gap must fail loudly at composition."""
    with pytest.raises(TypeError, match="required positional argument: 'session'"):
        build_smoke_gate()  # type: ignore[call-arg]  # deliberately omitting required session arg


def test_gate_covers_the_non_interactive_checks_and_omits_the_browser_smoke() -> None:
    gate = build_smoke_gate(_pool_aggregate())
    names = {name for name, _, _ in gate()}
    assert {
        "Python Version",
        "Playwright Chromium Browser",
        "Workspace Initialization",
        "Session Authentication Token",
        "Output Storage Permission",
        "Host Capacity",
        "Chromium Sandbox",
        "Environment Contract",
        "Observability Backends",
    } <= names
    assert "Browser Smoke Test" not in names


def test_gate_threads_the_pool_check_and_calls_the_aggregate_once() -> None:
    aggregate = _pool_aggregate(with_healthy_session=True)
    results = build_smoke_gate(aggregate)()
    by_name = {name: (passed, detail) for name, passed, detail in results}
    passed, detail = by_name["Session Authentication Token"]
    assert passed is True
    assert "1 healthy" in detail
    aggregate.execute.assert_called_once()


def test_gate_runs_checks_at_execution_time_not_construction_time() -> None:
    """Issue #506: the post-upgrade state is read inside the callable."""
    aggregate = _pool_aggregate()
    gate = build_smoke_gate(aggregate)
    aggregate.execute.assert_not_called()
    gate()
    aggregate.execute.assert_called_once()


# ─── ConfigHealthProbe.probe ──────────────────────────────────────────────


def test_probe_returns_frozen_health_probe_records() -> None:
    records = ConfigHealthProbe().probe()
    assert records
    for record in records:
        assert isinstance(record, HealthProbeRecord)
        assert record.severity in {"ok", "warning"}


def test_probe_without_a_session_omits_the_pool_check() -> None:
    names = {record.name for record in ConfigHealthProbe().probe()}
    assert "Session Authentication Token" not in names
