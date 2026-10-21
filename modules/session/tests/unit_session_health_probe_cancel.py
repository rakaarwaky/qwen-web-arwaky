"""Regression test: a stalled health probe must not leak its browser context.

SA-4-01: ``asyncio.wait_for`` cancels the future it wraps, but a
``loop.run_in_executor`` task cannot be cancelled, so a probe that stalled
inside navigation kept its Chromium context alive after the timeout verdict
returned. The probe must now observe a cooperative cancel handle between its
navigation steps and close its own context. The asyncio side sets the handle
in the timeout branch and gives the probe thread a bounded grace window.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
from modules.shared.src.session.taxonomy_session_vo import HealthReason, SessionInfo, SessionStatus


def _session() -> SessionInfo:
    return SessionInfo(
        session_id="unit-cancel",
        name="session-cancel",
        path=Path("/tmp/session-cancel"),
        status=SessionStatus.UNKNOWN,
        created_at=datetime(2026, 1, 1),
    )


class _StalledBrowser:
    """Browser seam whose probe blocks until the cancel handle is set.

    ``health_probe_page`` stands in for the adapter's launch → navigate
    sequence: the probe thread holds the context open exactly as long as the
    real one does when ``page.goto`` never returns, and records teardown in
    ``state`` so the test asserts on the stub rather than a process table.
    """

    def __init__(self) -> None:
        self.state = {"closed": False, "entered": threading.Event()}
        self._cancel: threading.Event | None = None

    def bind(self, cancel: threading.Event) -> None:
        self._cancel = cancel

    @contextmanager
    def health_probe_page(self, cfg: Any) -> Iterator[Any]:
        self.state["entered"].set()
        try:
            # The navigation equivalent of a wedged page.goto: park until the
            # probe's own cancel handle is set, then unwind out of the
            # context manager so its teardown runs on this thread.
            assert self._cancel is not None
            self._cancel.wait(timeout=30)
            yield MagicMock()
        finally:
            self.state["closed"] = True


class _NeverCancels(_StalledBrowser):
    """A probe that never observes any handle, like a wedged ``page.goto``."""

    @contextmanager
    def health_probe_page(self, cfg: Any) -> Iterator[Any]:
        self.state["entered"].set()
        try:
            threading.Event().wait(timeout=30)
            yield MagicMock()
        finally:
            self.state["closed"] = True


def _checker(browser: _StalledBrowser) -> SessionHealthChecker:
    checker = SessionHealthChecker(browser=browser, timeout_seconds=0.2)
    browser.bind(checker._cancel)
    return checker


def test_a_timed_out_probe_closes_its_browser_context() -> None:
    """The verdict returns TIMEOUT and the context closes within a bounded grace."""
    browser = _StalledBrowser()
    checker = _checker(browser)

    async def _run() -> object:
        return await checker.diagnose_session(_session())

    verdict = asyncio.run(_run())

    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.TIMEOUT.value
    assert browser.state["closed"] is True


def test_a_probe_that_ignores_the_cancel_does_not_hold_the_caller() -> None:
    """A wedged probe cannot keep the health check hostage past the grace window."""
    browser = _NeverCancels()
    checker = _checker(browser)

    async def _run() -> object:
        return await asyncio.wait_for(checker.diagnose_session(_session()), timeout=15)

    verdict = asyncio.run(_run())

    assert verdict.status == SessionStatus.AUTH_REQUIRED
    assert verdict.reason == HealthReason.TIMEOUT.value


def test_the_probe_thread_tears_its_own_context_down() -> None:
    """The context exit runs on the probe thread, never on the asyncio side."""
    browser = _StalledBrowser()
    checker = _checker(browser)
    teardown_thread: list[threading.Thread] = []
    original = browser.health_probe_page

    @contextmanager
    def _recording(cfg: Any) -> Iterator[Any]:
        with original(cfg) as page:
            yield page
        teardown_thread.append(threading.current_thread())

    browser.health_probe_page = _recording

    async def _run() -> object:
        return await checker.diagnose_session(_session())

    asyncio.run(_run())

    assert browser.state["closed"] is True
    assert teardown_thread, "the probe's context exit must run on the probe thread"
    assert teardown_thread[0] is not threading.main_thread()


def test_a_probe_that_succeeds_never_sees_the_cancel_handle() -> None:
    """The cancel handle stays unset on the happy path so no healthy run is aborted."""

    class _Healthy(_StalledBrowser):
        @contextmanager
        def health_probe_page(self, cfg: Any) -> Iterator[Any]:
            page = MagicMock()
            page.inner_text.return_value = "Qwen chat"
            page.query_selector.return_value = MagicMock()
            yield page

    browser = _Healthy()
    checker = _checker(browser)

    async def _run() -> object:
        return await checker.diagnose_session(_session())

    verdict = asyncio.run(_run())

    assert verdict.status == SessionStatus.ACTIVE
    assert checker._cancel.is_set() is False
