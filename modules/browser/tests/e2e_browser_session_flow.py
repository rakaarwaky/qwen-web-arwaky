"""End-to-end tests for the browser aggregate against a live page.

The aggregate's promise is that a caller never receives an unauthenticated
page. These drive the real `open_session` door over a local fixture page
with a stubbed browser seam, so no network and no saved session are needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.browser.src.agent_browser_orchestrator import BrowserOrchestrator
from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics
from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.browser.src.capabilities_browser_model_policy import BrowserModelPolicy
from modules.browser.src.capabilities_browser_navigation import BrowserNavigation
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig


def _make_orchestrator() -> BrowserOrchestrator:
    """Build a standalone BrowserOrchestrator for the e2e suite."""
    obs = MagicMock()
    obs.get_logger.return_value = MagicMock()
    diag = BrowserDiagnostics()
    model_policy = BrowserModelPolicy()
    lifecycle = BrowserLifecycle(navigation=None, diagnostics=diag)
    navigation = BrowserNavigation(model_policy=model_policy, lifecycle=lifecycle)
    lifecycle.navigation = navigation
    return BrowserOrchestrator(
        None, obs, lifecycle=lifecycle, navigation=navigation, model_policy=model_policy, diagnostics=diag
    )


_browser = _make_orchestrator()


@pytest.fixture
def live_page():
    """Return a page stub positioned on a real chat URL."""
    page = MagicMock()
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    page.url = "https://chat.qwen.ai/"
    page.locator.return_value.count.return_value = 0
    return page


@pytest.fixture
def cfg(tmp_path: Path) -> AppConfig:
    (tmp_path / "in.md").write_text("prompt", encoding="utf-8")
    return AppConfig(
        mode="single",
        input_path=tmp_path / "in.md",
        output_path=tmp_path / "out.md",
        session_path=tmp_path / "session",
        headless=True,
    )


def test_e2e_check_auth_passes_on_a_chat_page(live_page) -> None:
    _browser.check_auth(live_page)


def test_e2e_check_auth_raises_on_a_login_redirect(live_page) -> None:
    live_page.url = "https://chat.qwen.ai/login"
    with pytest.raises(AuthRequiredError):
        _browser.check_auth(live_page)


def test_e2e_check_session_reports_ready_for_a_live_chat(live_page) -> None:
    assert _browser.check_session(live_page) is True


def test_e2e_check_session_reports_not_ready_when_the_textarea_is_absent(live_page) -> None:
    live_page.query_selector.return_value = None
    assert _browser.check_session(live_page) is False
