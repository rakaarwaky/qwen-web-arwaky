"""Async event-loop isolation utilities.

Utility layer (utility_async_loop): stateless functions for event-loop
management in worker threads that host Playwright sync APIs.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress


def isolate_thread_event_loop() -> None:
    """Ensure the current thread has an isolated event loop for sync APIs."""
    with suppress(RuntimeError, AttributeError):
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
        asyncio.set_event_loop(asyncio.new_event_loop())
