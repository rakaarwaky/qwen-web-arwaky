"""Unit tests for the session-pool shortfall rule (FR-SWARM-003).

When the session pool offers fewer healthy sessions (N) than the clamped
browser count (B), the runner runs N legs, reports the shortfall on the
snapshot, and does not pad or reuse sessions. A known-LIMITED session is
never used. These tests pin the pure shortfall math plus the kernel
helpers that decide the submitted leg count, independent of a live pool.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from modules.shared.src.swarm.taxonomy_swarm_vo import (
    SwarmAgentSnapshot,
    SwarmId,
    SwarmSnapshot,
)
from modules.shared.src.swarm.utility_swarm_runner_base import (
    mark_agent_progress,
    mark_cancelled,
    replace_status,
)
from modules.swarm.src.capabilities_swarm_registry import SwarmRegistry
from modules.swarm.src.capabilities_swarm_runner import submitted_leg_count


def _snapshot() -> SwarmSnapshot:
    """A running snapshot with four legs and a clamped browser count of 4."""
    return SwarmSnapshot(
        swarm_id=SwarmId("swarm-test"),
        input_path=Path("/tmp/project.md"),
        root_path=Path("/tmp/swarm-test"),
        status="running",
        max_attempts=3,
        browser_concurrency=4,
        agents=tuple(
            SwarmAgentSnapshot(agent_id=role, status="queued", output_path=None)
            for role in ("architect", "security", "ux", "backend")
        ),
    )


def test_shortfall_reports_the_missing_legs() -> None:
    """When 3 healthy sessions back 4 requested legs, the shortfall is 1.

    The runner submits N legs (not B) and records B - N on the snapshot so
    a poller sees the shortfall instead of a padding/reuse decision.
    """
    submitted, shortfall = submitted_leg_count(requested_browsers=4, healthy_sessions=3)
    assert submitted == 3
    assert shortfall == 1


def test_shortfall_is_zero_when_the_pool_covers_the_count() -> None:
    """A pool with as many healthy sessions as requested legs reports no shortfall."""
    submitted, shortfall = submitted_leg_count(requested_browsers=4, healthy_sessions=6)
    assert submitted == 4
    assert shortfall == 0


def test_no_padding_below_one() -> None:
    """A request below one clamps to one leg rather than producing zero."""
    submitted, shortfall = submitted_leg_count(requested_browsers=0, healthy_sessions=1)
    assert submitted == 1
    assert shortfall == 0


def test_shortfall_never_exceeds_requested() -> None:
    """The shortfall is bounded by the requested count (N < B is the only regime)."""
    _, shortfall = submitted_leg_count(requested_browsers=10, healthy_sessions=2)
    assert shortfall == 8
    assert shortfall <= 10


def test_snapshot_preserves_shortfall_across_status_transitions() -> None:
    """The shortfall survives a leg progress update and a run-level cancel.

    Pinned so a future status rewrite cannot silently drop the reported
    shortfall from the snapshot a poller reads.
    """
    base = _snapshot()
    short = replace(base, session_shortfall=2)

    progressed = mark_agent_progress(short, "architect", "completed", 1, Path("/tmp/a.md"), None, 0.5)
    assert progressed.session_shortfall == 2

    cancelled = mark_cancelled(progressed)
    assert cancelled.session_shortfall == 2


def test_replace_status_keeps_the_shortfall() -> None:
    """A run-level status rewrite carries the shortfall forward unchanged."""
    base = _snapshot()
    short = replace(base, session_shortfall=3)
    running = replace_status(short, "running")
    assert running.session_shortfall == 3


def test_shortfall_round_trips_through_the_registry() -> None:
    """A shortfall written by the runner survives a registry read.

    The start seam persists the initial snapshot with the shortfall; the
    progress seam then reports it back to the caller.
    """
    registry = SwarmRegistry()
    submitted, shortfall = submitted_leg_count(requested_browsers=5, healthy_sessions=2)
    assert submitted == 2 and shortfall == 3

    snapshot = _snapshot()
    snapshot = replace(snapshot, browser_concurrency=submitted, session_shortfall=shortfall)
    registry.open_run(snapshot, {}, Path("/tmp/attach.md"))

    read = registry.get_snapshot(SwarmId("swarm-test"))
    assert read is not None
    assert read.session_shortfall == 3
    assert read.browser_concurrency == 2


def test_shortfall_is_persisted_in_the_manifest_payload() -> None:
    """The manifest that a disk reader sees carries the shortfall field."""
    from modules.shared.src.swarm.utility_swarm_runner_base import _manifest_payload

    snapshot = _snapshot()
    snapshot = replace(snapshot, session_shortfall=4)
    payload = _manifest_payload(snapshot)
    assert payload["session_shortfall"] == 4


def test_shortfall_matrix() -> None:
    """The rule is total: submitted = min(max(requested, 1), healthy)."""
    cases = [
        (4, 3, 3, 1),
        (4, 6, 4, 0),
        (0, 1, 1, 0),
        (10, 2, 2, 8),
        (1, 1, 1, 0),
        (5, 0, 0, 5),
    ]
    for requested, healthy, expected_submitted, expected_shortfall in cases:
        submitted, shortfall = submitted_leg_count(requested_browsers=requested, healthy_sessions=healthy)
        assert submitted == expected_submitted, (requested, healthy, submitted)
        assert shortfall == expected_shortfall, (requested, healthy, shortfall)
