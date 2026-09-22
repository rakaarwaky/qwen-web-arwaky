"""Capability layer (run cancel registry): thread-safe targeted cancel for concurrent runs.

Implements IRunCancelProtocol.  Owns the shared bookkeeping that the prompt
file, attachment, and swarm orchestrators need to stop one in-flight run's
browser context without touching sibling runs on the same instance.

``RunState`` is a taxonomy value object (``taxonomy_core_vo``); this module
adds only the thread-safe registry and the cancel action.
"""

from __future__ import annotations

import contextlib
import threading

from modules.shared.src.contract_core_protocol import IRunCancelProtocol
from modules.shared.src.taxonomy_core_vo import RunState


class RunCancelRegistry:
    """Thread-safe registry of active runs keyed by their cancel event.

    Entries are keyed on the caller's ``threading.Event`` object itself, never
    on ``id()`` (whose address is recycled once an event is garbage
    collected), so a cancel targets one specific in-flight run.
    """

    def __init__(self) -> None:
        self._states: dict[threading.Event, RunState] = {}
        self._lock = threading.Lock()

    def register(self, run_state: RunState) -> None:
        """Track a newly started in-flight run."""
        with self._lock:
            self._states[run_state.cancel_event] = run_state

    def release(self, run_state: RunState) -> None:
        """Drop the entry for a finished run."""
        with self._lock:
            self._states.pop(run_state.cancel_event, None)

    def active_bctx(self, cancel_event: threading.Event) -> object | None:
        """Return the live browser context registered for this event, or None."""
        with self._lock:
            run_state = self._states.get(cancel_event)
        if run_state is None:
            return None
        with run_state.bctx_lock:
            return run_state.active_bctx

    def set_active_bctx(self, cancel_event: threading.Event, bctx: object | None) -> None:
        """Update the browser context for a registered run (None clears it)."""
        with self._lock:
            run_state = self._states.get(cancel_event)
        if run_state is None:
            return
        with run_state.bctx_lock:
            run_state.active_bctx = bctx

    def cancel_run(self, cancel_event: threading.Event) -> None:
        """Cancel one specific in-flight run identified by its event.

        The event is always set so any in-progress flow check observes the new
        state, even when the run already finished.  When the run is still
        active, its browser context is closed so the underlying browser
        process stops.  Sibling runs holding different events are unaffected.
        """
        with self._lock:
            run_state = self._states.get(cancel_event)
        if run_state is None:
            cancel_event.set()
            return
        cancel_event.set()
        bctx = self.active_bctx(cancel_event)
        if bctx is not None:
            close_fn = getattr(bctx, "close", None)
            if callable(close_fn):
                with contextlib.suppress(Exception):
                    close_fn()

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
