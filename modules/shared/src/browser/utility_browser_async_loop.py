"""Async event-loop isolation utilities.

Utility layer (utility_async_loop): stateless functions for event-loop
management in worker threads that host Playwright sync APIs.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress


def isolate_thread_event_loop() -> None:
    """Ensure the current thread has an isolated event loop for sync APIs.

    Uses only the public ``asyncio`` API so the behaviour is stable across
    Python versions (the previous implementation reached into the private
    ``asyncio._set_running_loop`` slot, which is not guaranteed to exist).
    """
    with suppress(RuntimeError, AttributeError):
        asyncio.set_event_loop(asyncio.new_event_loop())
