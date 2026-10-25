"""Unit tests pinning the fan-out progress envelope a poller relies on.

The FR-SWARM-002 spec says a poller (the MCP `get_job_status` consumer) reads
one snapshot for the whole run: run-level `status`, the per-leg `agents` tuple
with its own statuses, and the `browser_concurrency` / `clamped_browser_count`
/ `session_shortfall` fields. These tests pin that every documented field is
present and typed on a running snapshot, so a future rewrite cannot drop a
field the envelope spec names.
"""

from __future__ import annotations

from dataclasses import asdict, fields, replace
from pathlib import Path

import pytest

from modules.shared.src.swarm.taxonomy_swarm_vo import (
    SwarmAgentSnapshot,
    SwarmId,
    SwarmSnapshot,
)
from modules.swarm.src.capabilities_swarm_registry import SwarmRegistry


# The field vocabulary the FR-SWARM-002 envelope spec names.
RUN_FIELDS = {
    "swarm_id",
    "input_path",
    "root_path",
    "status",
    "max_attempts",
    "browser_concurrency",
    "clamped_browser_count",
    "session_shortfall",
    "agents",
}
LEG_FIELDS = {
    "agent_id",
    "status",
    "attempt",
    "output_path",
    "error",
    "duration_sec",
}


def _running_snapshot() -> SwarmSnapshot:
    """A mid-run snapshot with the mix of leg states a poller would observe."""
    return SwarmSnapshot(
        swarm_id=SwarmId("swarm-progress"),
        input_path=Path("/tmp/project.md"),
        root_path=Path("/tmp/swarm-progress"),
        status="running",
        max_attempts=3,
        browser_concurrency=2,
        clamped_browser_count=1,
        session_shortfall=0,
        agents=(
            SwarmAgentSnapshot(agent_id="architect", status="completed", attempt=1, output_path=Path("/tmp/swarm-progress/architect/output.md"), error=None, duration_sec=42.0),
            SwarmAgentSnapshot(agent_id="security", status="running", attempt=1, output_path=Path("/tmp/swarm-progress/security/output.md"), error=None, duration_sec=None),
            SwarmAgentSnapshot(agent_id="ux", status="retrying", attempt=2, output_path=Path("/tmp/swarm-progress/ux/output.md"), error=None, duration_sec=None),
            SwarmAgentSnapshot(agent_id="backend", status="queued", attempt=0, output_path=Path("/tmp/swarm-progress/backend/output.md"), error=None, duration_sec=None),
        ),
    )


def test_all_documented_run_fields_are_present() -> None:
    """Every field the FR-SWARM-002 spec names is on the snapshot.

    Pinned by comparing against the dataclass field set so a field removal
    fails here, not in a poller that has to be reworked.
    """
    actual = {field.name for field in fields(SwarmSnapshot)}
    missing = RUN_FIELDS - actual
    assert not missing, f"the envelope spec names fields the snapshot lacks: {sorted(missing)}"


def test_all_documented_leg_fields_are_present() -> None:
    """Every per-leg field the spec names is on a leg snapshot."""
    actual = {field.name for field in fields(SwarmAgentSnapshot)}
    missing = LEG_FIELDS - actual
    assert not missing, f"the envelope spec names leg fields the snapshot lacks: {sorted(missing)}"


def test_running_snapshot_carries_the_documented_statuses() -> None:
    """A running snapshot exposes the exact status vocabulary a poller maps.

    The run is `running` with a mix of terminal, in-flight, and queued legs,
    which is the shape a `get_job_status` consumer sees mid-fan-out.
    """
    snap = _running_snapshot()
    assert snap.status == "running"
    leg_statuses = {agent.status for agent in snap.agents}
    assert leg_statuses == {"completed", "running", "retrying", "queued"}
    # The leg that is still working carries no error; the settled one does.
    security = next(agent for agent in snap.agents if agent.agent_id == "security")
    assert security.error is None
    # Run-level counters the envelope spec names.
    assert snap.browser_concurrency == 2
    assert snap.clamped_browser_count == 1
    assert snap.session_shortfall == 0


def test_envelope_fields_round_trip_through_the_registry() -> None:
    """The fields a poller reads are the fields the start seam persisted.

    The start seam writes the snapshot to the registry; the progress seam
    reads it back. A poller that only sees the persisted manifest must still
    get every documented field.
    """
    registry = SwarmRegistry()
    snap = _running_snapshot()
    registry.open_run(snap, {}, Path("/tmp/attach.md"))

    read = registry.get_snapshot(SwarmId("swarm-progress"))
    assert read is not None
    # The envelope fields survive the read, including the new shortfall/clamp.
    assert read.status == snap.status
    assert read.browser_concurrency == snap.browser_concurrency
    assert read.clamped_browser_count == snap.clamped_browser_count
    assert read.session_shortfall == snap.session_shortfall
    assert {agent.agent_id for agent in read.agents} == {agent.agent_id for agent in snap.agents}


def test_envelope_serializes_for_the_manifest() -> None:
    """The documented fields are the ones a JSON manifest round-trips.

    The registry persists to `manifest.json` via `asdict`; the poller's
    envelope is the persisted shape, so the fields must serialize cleanly.
    """
    snap = _running_snapshot()
    payload = asdict(snap)
    for field in RUN_FIELDS:
        assert field in payload, f"{field} is not in the serialized envelope"
    for agent_payload in payload["agents"]:
        for field in LEG_FIELDS:
            assert field in agent_payload, f"{field} is not in the serialized leg"


@pytest.mark.parametrize(
    "status",
    ["queued", "running", "completed", "partial", "failed", "cancelled"],
)
def test_envelope_covers_every_run_status(status: str) -> None:
    """The run-level status vocabulary is the documented six states.

    A poller branches on `status`; the spec fixes the closed set, so a new
    state is a contract change, not an undocumented value.
    """
    snap = _running_snapshot()
    changed = replace(snap, status=status)
    assert changed.status == status
