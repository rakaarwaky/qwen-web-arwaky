"""Capability layer (run cancel registry): thread-safe targeted cancel for concurrent runs.

Implements IRunCancelProtocol.  Owns the shared bookkeeping that the prompt
file, attachment, and swarm orchestrators need to stop one in-flight run's
browser context without touching sibling runs on the same instance.

``RunState`` is a taxonomy value object (``taxonomy_core_vo``); this module
adds only the thread-safe registry and the cancel action.  Lookups are keyed
by the stable ``run_id`` on each ``RunState`` so cancellation is robust even
if the caller reuses or recreates the original ``threading.Event``.
"""

from __future__ import annotations

import contextlib
import threading

from modules.shared.src.contract_core_protocol import IRunCancelProtocol
from modules.shared.src.taxonomy_core_vo import RunId, RunState


class RunCancelRegistry:
    """Thread-safe registry of active runs keyed by their run_id.

    Entries are keyed on ``run_state.run_id``, never on ``id()`` of an
    object, so a cancel targets one specific in-flight run even when events
    are recreated across threads.  A private event-index supports the
    ``request_cancel`` convenience path used by surfaces that only hold the
    original ``threading.Event``.
    """

    def __init__(self) -> None:
        self._states: dict[RunId, RunState] = {}
        self._event_index: dict[threading.Event, RunId] = {}
        self._lock = threading.Lock()

    def register(self, run_state: RunState) -> None:
        """Track a newly started in-flight run."""
        with self._lock:
            self._states[run_state.run_id] = run_state
            if run_state.cancel_event is not None:
                self._event_index[run_state.cancel_event] = run_state.run_id

    def release(self, run_state: RunState) -> None:
        """Drop the entry for a finished run."""
        with self._lock:
            self._states.pop(run_state.run_id, None)
            if run_state.cancel_event is not None:
                self._event_index.pop(run_state.cancel_event, None)

    def active_bctx(self, run_id: RunId) -> object | None:
        """Return the live browser context registered for this run_id, or None."""
        with self._lock:
            run_state = self._states.get(run_id)
        if run_state is None:
            return None
        with run_state.bctx_lock:
            return run_state.active_bctx

    def set_active_bctx(self, run_id: RunId, bctx: object | None) -> None:
        """Update the browser context for a registered run (None clears it)."""
        with self._lock:
            run_state = self._states.get(run_id)
        if run_state is None:
            return
        with run_state.bctx_lock:
            run_state.active_bctx = bctx

    def cancel_run(self, run_id: RunId) -> None:
        """Cancel one specific in-flight run identified by its run_id.

        The run's ``cancel_event`` is always set so any in-progress flow
        check observes the new state, even when the run already finished.
        When the run is still active, its browser context is closed so the
        underlying browser process stops.  Sibling runs holding different
        run_ids are unaffected.
        """
        with self._lock:
            run_state = self._states.get(run_id)
        if run_state is None:
            return
        run_state.cancel_event.set()
        bctx = self.active_bctx(run_id)
        if bctx is not None:
            close_fn = getattr(bctx, "close", None)
            if callable(close_fn):
                with contextlib.suppress(Exception):
                    close_fn()

    def cancel_by_event(self, cancel_event: threading.Event) -> None:
        """Cancel the run whose ``cancel_event`` was supplied.

        Delegates to ``cancel_run`` using the stable run_id resolved from
        the internal event index.  If the event is not registered the run
        has already finished and the call is a no-op.
        """
        with self._lock:
            run_id = self._event_index.get(cancel_event)
        if run_id is None:
            return
        self.cancel_run(run_id)

    def __repr__(self) -> str:
        return f"RunCancelRegistry(active={len(self._states)})"


class CapabilitiesRunCancelRegistry(RunCancelRegistry, IRunCancelProtocol):
    """Capability facade exposing the targeted-cancel registry.

    Satisfies ``IRunCancelProtocol`` for orchestrators that take the protocol
    as a constructor dependency.  Behavior is inherited from
    ``RunCancelRegistry``.
    """

    def __init__(self) -> None:
        RunCancelRegistry.__init__(self)


__all__ = ["CapabilitiesRunCancelRegistry", "RunCancelRegistry"]
