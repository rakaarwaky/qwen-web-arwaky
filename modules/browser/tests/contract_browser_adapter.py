"""Contract tests for the browser orchestrator's public seam.

Pins the aggregate surface a caller may depend on, so a signature
change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from modules.browser.src.agent_browser_orchestrator import BrowserOrchestrator
from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics
from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.browser.src.capabilities_browser_model_policy import BrowserModelPolicy
from modules.browser.src.capabilities_browser_navigation import BrowserNavigation
from modules.shared.src.browser.contract_browser_aggregate import IBrowserAggregate

_REQUIRED_PROTOCOL_METHODS: frozenset[str] = frozenset(
    {
        "browser_session",
        "check_auth",
        "check_session",
        "detect_session_expired",
        "health_probe_page",
        "navigate_to_chat",
        "open_chat_page",
        "open_login_page",
        "renew_session",
        "reset_page",
        "select_model",
        "verify_model",
        "wire_diagnostics",
    }
)


def _make_orchestrator() -> BrowserOrchestrator:
    """Build a BrowserOrchestrator with all narrow capability views wired."""
    obs = MagicMock()
    diag = BrowserDiagnostics()
    lifecycle = BrowserLifecycle(navigation=None, diagnostics=diag)
    model_policy = BrowserModelPolicy()
    navigation = BrowserNavigation(model_policy=model_policy, lifecycle=lifecycle)
    lifecycle.navigation = navigation
    return BrowserOrchestrator(
        obs,
        lifecycle=lifecycle,
        navigation=navigation,
        model_policy=model_policy,
        diagnostics=diag,
    )


def test_aggregate_declares_only_the_open_session_door() -> None:
    public = {name for name, _ in inspect.getmembers(IBrowserAggregate, predicate=inspect.isfunction)}
    assert public == {"open_session"}
