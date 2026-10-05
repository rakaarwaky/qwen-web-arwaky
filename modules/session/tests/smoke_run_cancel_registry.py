"""Smoke tests for the session run-cancel registry.

The registry is what makes a fan-out leg cancelable without cancelling its
siblings, so the smoke path is "register, cancel, release, and confirm the
registry is empty afterwards".
"""

from __future__ import annotations

from modules.session.src.capabilities_run_cancel_registry import RunCancelRegistry
from modules.shared.src.taxonomy_core_vo import RunState


def _state(run_id: str) -> RunState:
    return RunState(run_id=run_id)


def test_smoke_registering_and_releasing_leaves_the_registry_empty() -> None:
    registry = RunCancelRegistry()
    state = _state("run-1")

    registry.register(state)
    registry.release(state)

    assert registry.active_bctx("run-1") is None


def test_smoke_a_registered_run_exposes_its_browser_context() -> None:
    registry = RunCancelRegistry()
    state = _state("run-1")
    state.active_bctx = object()

    registry.register(state)

    assert registry.active_bctx("run-1") is state.active_bctx


def test_smoke_cancelling_an_unregistered_run_is_a_no_op() -> None:
    registry = RunCancelRegistry()

    registry.cancel_run("never-registered")

    assert registry.active_bctx("never-registered") is None


def test_smoke_cancelling_a_registered_run_sets_its_event() -> None:
    registry = RunCancelRegistry()
    state = _state("run-1")
    registry.register(state)

    registry.cancel_run("run-1")

    assert state.cancel_event.is_set()
