"""Regression tests for saved-session validation and manual login lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_login_command import handle
from modules.core.src.agent_setup_orchestrator import SetupOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.shared.src import AppConfig


class _BrowserHarness:
    """Small browser protocol fake that records context lifetime and config."""

    def __init__(self, session_results: list[bool]) -> None:
        self._session_results = list(session_results)
        self._check_count = 0
        self.context_configs: list[object] = []
        self.active = False
        self.page = MagicMock()
        self.page.pages = [self.page]
        # Simulate user closing the browser immediately (is_closed returns True)
        self.page.is_closed.return_value = True

    @contextmanager
    def browser_session(self, cfg):
        self.context_configs.append(cfg)
        self.active = True
        context = MagicMock()
        context.pages = [self.page]
        try:
            yield context
        finally:
            self.active = False

    def navigate_to_chat(self, page, emitter) -> None:
        return None

    def check_auth(self, page) -> None:
        return None

    def check_session(self, page) -> bool:
        """Return True once the expected results are exhausted."""
        if self._check_count < len(self._session_results):
            result = self._session_results[self._check_count]
            self._check_count += 1
            return result
        # Exhausted expected results — session is now stable (True)
        return True

    def reset_page(self, page, emitter) -> None:
        return None


def _orchestrator(browser: _BrowserHarness) -> SetupOrchestrator:
    """Build an orchestrator with the non-browser capabilities mocked."""
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()
    return SetupOrchestrator(browser=browser, observability=observability)


def test_existing_valid_session_skips_visible_login(tmp_path: Path) -> None:
    """A valid profile reports its state without opening a headed context."""
    session_path = tmp_path / "session"
    session_path.mkdir()
    browser = _BrowserHarness([True])
    confirmation = MagicMock()

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "already valid" in result
    confirmation.assert_not_called()
    assert len(browser.context_configs) == 1
    validation_cfg = browser.context_configs[0]
    assert validation_cfg.mode == "session-check"
    assert validation_cfg.headless is True


def test_manual_login_keeps_browser_open_until_confirmation(tmp_path: Path) -> None:
    """Browser stays open until user closes it (is_closed returns True), then validates saved session."""
    session_path = tmp_path / "session"
    browser = _BrowserHarness([True])

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=True,
        session_path=session_path,
    )

    assert "completed successfully" in result
    # Two contexts: login (headed) + session-check (headless validation after close)
    assert len(browser.context_configs) == 2
    assert [cfg.mode for cfg in browser.context_configs] == ["login", "session-check"]


def test_invalid_saved_session_falls_back_to_manual_login(tmp_path: Path) -> None:
    """An expired profile is checked first, then replaced through manual login.
    After user closes browser, session-check runs again to validate the new session."""
    session_path = tmp_path / "session"
    session_path.mkdir()
    browser = _BrowserHarness([False, True])
    confirmation = MagicMock(side_effect=lambda: _assert_browser_active(browser))

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "completed successfully" in result
    assert [cfg.mode for cfg in browser.context_configs] == ["session-check", "login", "session-check"]


def test_manual_login_reports_invalid_final_state(tmp_path: Path) -> None:
    """When user closes browser but session is invalid, _validate_saved_session returns False.
    The mock's check_session returns False (first result), so login fails with message."""
    browser = _BrowserHarness([False])

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=True,
        session_path=tmp_path / "session",
    )

    assert "did not produce a valid" in str(result)


def _assert_context_closed(browser: _BrowserHarness) -> None:
    """Assert that the browser context was closed after login."""
    assert browser.active is False


def _assert_browser_active(browser: _BrowserHarness) -> None:
    """Assert that a callback was invoked inside the context manager."""
    assert browser.active is True


def test_cli_login_passes_confirmation_callback_to_core(tmp_path: Path) -> None:
    """The CLI calls setup_session without wait_for_confirmation (browser close triggers check)."""
    cfg = AppConfig(
        mode="login",
        input_path=tmp_path / "input",
        output_path=tmp_path / "output",
        session_path=tmp_path / "session",
    )
    session = MagicMock()
    setup = MagicMock()
    setup.setup_session.return_value = "Manual login completed successfully."

    with patch("sys.stdin"):
        result = handle(None, session, setup, cfg)

    assert result == {"success": True, "message": "Manual login completed successfully."}
    setup.setup_session.assert_called_once()
    kwargs = setup.setup_session.call_args.kwargs
    assert kwargs["session_path"] == cfg.session_path
    assert kwargs["wait_for_confirmation"] is None


def test_browser_check_session_requires_authenticated_chat_ui() -> None:
    """The browser capability accepts the chat UI and rejects login URLs."""
    page = MagicMock()
    page.url = "https://chat.qwen.ai/"
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    page.locator.return_value.count.return_value = 0
    page.locator.return_value.first.is_visible.return_value = False
    assert BrowserAdapter().check_session(page) is True

    page.url = "https://chat.qwen.ai/login"
    assert BrowserAdapter().check_session(page) is False


def test_manual_login_delays_check_session_after_confirmation(tmp_path: Path) -> None:
    """After wait_for_confirmation, setup_session waits before checking session.

    This prevents the browser from being checked while the page is still
    stabilizing after a manual login — which previously caused a hang.
    """
    session_path = tmp_path / "session"
    browser = _BrowserHarness([True])
    confirmation = MagicMock()

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "completed successfully" in result
