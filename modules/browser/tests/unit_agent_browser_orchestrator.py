"""Unit tests for BrowserOrchestrator: session open, teardown, and auth check."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Page

from modules.browser.src.agent_browser_orchestrator import BrowserOrchestrator
from modules.shared.src.taxonomy_core_vo import AppConfig


def _cfg() -> AppConfig:
    """Build a minimal AppConfig for adapter calls."""
    return AppConfig(
        mode="prompt-direct",
        input_path=Path("/tmp/in.md"),
        output_path=Path("/tmp/out.md"),
        session_path=Path("/tmp/session"),
        log_path=Path("/tmp/log.log"),
        interval=3,
        timeout=300,
        headless=True,
        chrome_profile="qwen-cli-profile",
        disable_sandbox=True,
        request_timeout=600,
        poll_interval=1.0,
        streaming_timeout=180,
        rate_limit_per_minute=60,
        circuit_breaker_threshold=5,
        circuit_breaker_window=30,
        storage_state_file=None,
    )


def _browser(page: Page | None = None) -> Any:
    """Return a stub browser whose browser_session yields ``page``."""
    bctx = MagicMock()
    bctx.pages = [page] if page is not None else []
    stub = MagicMock()
    stub.browser_session.return_value.__enter__.return_value = bctx
    return stub


def test_open_session_yields_first_page() -> None:
    page = MagicMock(spec=Page)
    bctx = MagicMock()
    bctx.pages = [page, MagicMock()]
    stub = MagicMock()
    stub.browser_session.return_value.__enter__.return_value = bctx

    with BrowserOrchestrator(stub).open_session(_cfg()) as got:
        assert got is page


def test_open_session_creates_page_when_context_is_empty() -> None:
    bctx = MagicMock()
    bctx.pages = []
    bctx.new_page.return_value = MagicMock(spec=Page)
    stub = MagicMock()
    stub.browser_session.return_value.__enter__.return_value = bctx

    with BrowserOrchestrator(stub).open_session(_cfg()) as got:
        assert got is bctx.new_page.return_value
    bctx.new_page.assert_called_once()


def test_open_session_closes_browser_on_exception() -> None:
    bctx = MagicMock()
    bctx.pages = [MagicMock(spec=Page)]
    manager = MagicMock()
    manager.__enter__.return_value = bctx
    stub = MagicMock()
    stub.browser_session.return_value = manager

    with pytest.raises(ValueError, match="boom"):
        with BrowserOrchestrator(stub).open_session(_cfg()):
            raise ValueError("boom")

    manager.__exit__.assert_called_once()


def test_check_session_delegates_to_capability() -> None:
    stub = _browser()
    stub.check_session.return_value = True
    page = MagicMock(spec=Page)

    assert BrowserOrchestrator(stub).check_session(page) is True
    stub.check_session.assert_called_once_with(page)


def test_navigate_to_chat_runs_auth_check_after_navigation() -> None:
    stub = _browser()
    order: list[str] = []
    stub.navigate_to_chat.side_effect = lambda *_a, **_k: order.append("navigate")
    stub.check_auth.side_effect = lambda *_a, **_k: order.append("auth")
    page = MagicMock(spec=Page)
    emitter = MagicMock()

    BrowserOrchestrator(stub).navigate_to_chat(page, emitter)

    assert order == ["navigate", "auth"]
