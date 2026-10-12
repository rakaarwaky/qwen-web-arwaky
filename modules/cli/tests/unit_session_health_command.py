"""Regression test: ``session health`` must probe through a real browser.

``cmd_health_check`` constructs ``SessionHealthChecker`` in-process (the CLI
Surface cannot import the Root container, AES205). A checker without an
injected ``browser`` seam is inert — ``check_session`` short-circuits to
``False`` — so the command must pass a real ``BrowserAdapter`` or every
session would be marked rate-limited on a healthy pool.

This test patches the ``SessionHealthChecker`` constructor to capture the
``browser=`` keyword argument and assert it is a ``BrowserAdapter``, while
injecting a fake page seam so no Chromium launch actually happens.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
from modules.cli.src.surface_cli_sessions_command import cmd_health_check
from modules.session.src.capabilities_session_health_checker import SessionHealthChecker


def _fake_browser_seam() -> MagicMock:
    """A fake browser seam whose probe yields a clean, authenticated chat page."""
    page = MagicMock()
    page.inner_text.return_value = "Qwen chat"
    page.query_selector.return_value = MagicMock()
    page.wait_for_timeout.return_value = None

    @contextlib.contextmanager
    def health_probe_page(cfg):
        yield page

    browser = MagicMock()
    browser.health_probe_page = health_probe_page
    return browser


def test_cmd_health_check_passes_a_real_browser_seam() -> None:
    """cmd_health_check must construct a BrowserAdapter and hand it to the checker."""
    manager = MagicMock()
    session = MagicMock()
    session.session_id = "session_1"
    manager.list_sessions.return_value = [session]

    captured: dict[str, object] = {}

    def _ctor_spy(*args, **kwargs):
        # Pin that the browser kwarg is a real BrowserAdapter instance.
        captured["browser_arg"] = kwargs.get("browser")
        # Swap in a fake page seam so the probe doesn't launch Chromium.
        fake_seam = _fake_browser_seam()
        other = {k: v for k, v in kwargs.items() if k != "browser"}
        checker = SessionHealthChecker(browser=fake_seam, **other)
        captured["checker"] = checker
        return checker

    with patch(
        "modules.session.src.capabilities_session_health_checker.SessionHealthChecker",
        side_effect=_ctor_spy,
    ):
        rc = cmd_health_check(manager)

    assert rc == 0
    # The command passed a BrowserAdapter as the browser seam.
    assert isinstance(captured.get("browser_arg"), BrowserAdapter), (
        "cmd_health_check must pass a BrowserAdapter so probes actually run"
    )
    # A healthy fake page marks the session healthy, not limited.
    manager.mark_healthy.assert_called_once_with("session_1")
    manager.mark_limited.assert_not_called()
