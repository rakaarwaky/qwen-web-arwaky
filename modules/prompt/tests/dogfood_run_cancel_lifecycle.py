"""Dogfood tests for the run-cancel registry against real threads and events.

The unit and smoke suites exercise the registry's bookkeeping with plain
objects; these drive it the way an actual run uses it — worker threads
parked on a real `threading.Event`, browser-context sentinels whose
`close()` closes a real `threading.Event`, and real cancellation tokens.
No live chat session is opened, so the registry is proven against the
real concurrency resources it exists to coordinate.
"""

from __future__ import annotations

import threading

from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.shared.src.common.taxonomy_core_vo import RunId, RunState


class _ContextSentinel:
    """A browser-context stand-in holding a real closable resource."""

    def __init__(self) -> None:
        self.closed = threading.Event()

    def close(self) -> None:
        """Close the underlying resource — the same verb a Playwright context exposes."""
        self.closed.set()


def _parked_run(run_id: str) -> tuple[RunState, _ContextSentinel, threading.Thread]:
    """A run whose worker thread blocks on the run's real cancel event."""
    state = RunState(run_id=RunId(run_id))
    bctx = _ContextSentinel()
    worker = threading.Thread(target=state.cancel_event.wait, name=f"run-{run_id}", daemon=True)
    worker.start()
    return state, bctx, worker


def test_dogfood_cancelling_one_run_parks_its_sibling_untouched() -> None:
    """Two live runs on one registry: cancelling A wakes A's thread and
    closes A's context; B's thread stays parked and B's context stays
    open until its own event is set."""
    registry = CapabilitiesRunCancelRegistry()
    run_a, bctx_a, thread_a = _parked_run("run-aaa1")
    run_b, bctx_b, thread_b = _parked_run("run-bbb2")
    registry.register(run_a)
    registry.register(run_b)
    registry.set_active_bctx(run_a.run_id, bctx_a)
    registry.set_active_bctx(run_b.run_id, bctx_b)

    stopped = registry.cancel_by_event(run_a.cancel_event)

    assert stopped is True, "the in-flight run must be reported as stopped"
    thread_a.join(timeout=2)
    assert not thread_a.is_alive(), "A's worker must wake by its real event being set"
    assert bctx_a.closed.is_set(), "A's context must be closed by the cancel"
    assert not bctx_b.closed.is_set(), "B's context must survive a cancel aimed at A"
    assert not run_b.cancel_event.is_set(), "B's event must stay unset"
    assert thread_b.is_alive(), "B's worker must still be parked"

    run_b.cancel_event.set()
    thread_b.join(timeout=2)
    registry.release(run_a)
    registry.release(run_b)
    assert registry.active_bctx(run_a.run_id) is None
    assert registry.active_bctx(run_b.run_id) is None


def test_dogfood_a_cancel_after_the_run_release_stops_nothing() -> None:
    """A run that reached a terminal state reports zero stopped
    pipelines: the registry answers False and leaves the real event unset,
    so no already-finished worker is spuriously woken."""
    registry = CapabilitiesRunCancelRegistry()
    state, bctx, worker = _parked_run("run-fin3")
    registry.register(state)
    registry.set_active_bctx(state.run_id, bctx)
    registry.release(state)

    stopped = registry.cancel_by_event(state.cancel_event)

    assert stopped is False, "a terminal run must report zero stopped pipelines"
    assert not state.cancel_event.is_set(), "a terminal cancel must not set the worker's event"
    assert not bctx.closed.is_set(), "a terminal cancel must not close a released context"
    assert worker.is_alive(), "the parked worker is untouched until its own event is set"

    state.cancel_event.set()
    worker.join(timeout=2)


def test_dogfood_a_reused_slot_event_still_cancels_the_live_job() -> None:
    """One TUI slot reuses a single event across sequential jobs
    (FR-PROMPT-005): releasing the predecessor must not strand the
    successor — a cancel through the shared token still stops the live
    job and closes only its context."""
    registry = CapabilitiesRunCancelRegistry()
    slot_event = threading.Event()
    first = RunState(run_id=RunId("slot-run-1"), cancel_event=slot_event)
    second = RunState(run_id=RunId("slot-run-2"), cancel_event=slot_event)
    first_ctx = _ContextSentinel()
    second_ctx = _ContextSentinel()

    registry.register(first)
    registry.register(second)
    registry.set_active_bctx(first.run_id, first_ctx)
    registry.set_active_bctx(second.run_id, second_ctx)
    registry.release(first)

    stopped = registry.cancel_by_event(slot_event)

    assert stopped is True, "the live job behind the reused event must still be cancellable"
    assert second_ctx.closed.is_set(), "the successor's context must close"
    assert not first_ctx.closed.is_set(), "the released predecessor's context must stay untouched"
    assert slot_event.is_set(), "the shared slot event ends set so the successor's worker wakes"
