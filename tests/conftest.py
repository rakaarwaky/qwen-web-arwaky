"""Shared pytest fixtures for the QwenClient behavior-lock regression suite.

Fixtures layered cleanly across:
1. Browser Layer (browser_ctx, page, client)
2. Pipeline Layer (fixture_root, cfg, audit, run_ctx)
3. E2E Layer (e2e_cfg)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import contextlib

from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics
from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.browser.src.capabilities_browser_model_policy import BrowserModelPolicy
from modules.browser.src.capabilities_browser_navigation import BrowserNavigation
from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter
from modules.prompt.src.capabilities_output_saver import Saver
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.prompt_runtime.src.capabilities_prompt_injector import PromptInjector
from modules.prompt_runtime.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt_runtime.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src import AppConfig, RunContext
from modules.shared.src.browser.utility_browser_async_loop import isolate_thread_event_loop
from modules.shared.src.common.utility_core_status import status_path_for
from tests.pipeline_fixtures import restore_fixture_state

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
FIXTURE = (FIXTURE_ROOT / "qwen_fixture.html").as_uri()


@pytest.fixture(scope="session")
def browser_ctx() -> BrowserContext:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        yield ctx
        with contextlib.suppress(Exception):
            ctx.close()


@pytest.fixture(autouse=True, scope="session")
def _reset_event_loop_at_session_end():
    """Reset asyncio event loop after session to prevent cross-module contamination."""
    yield
    isolate_thread_event_loop()


@pytest.fixture
def page(browser_ctx: BrowserContext):
    pg = browser_ctx.new_page()
    pg.goto(FIXTURE, wait_until="domcontentloaded")
    pg.wait_for_timeout(200)
    yield pg
    with contextlib.suppress(Exception):
        pg.close()


def _make_browser_views():
    """Build the narrow browser views the DirectPromptAdapter fixture needs."""
    diag = BrowserDiagnostics()
    model_policy = BrowserModelPolicy()
    lifecycle = BrowserLifecycle(navigation=None, diagnostics=diag)
    navigation = BrowserNavigation(model_policy=model_policy, lifecycle=lifecycle)
    lifecycle.navigation = navigation
    return lifecycle, navigation, diag


@pytest.fixture
def client(browser_ctx: BrowserContext, page) -> DirectPromptAdapter:
    cfg = AppConfig(
        mode="batch",
        input_path=ROOT / "input",
        output_path=ROOT / "output",
        session_path=ROOT / "qwen_session",
        headless=True,
    )
    lifecycle, navigation, diag = _make_browser_views()
    return DirectPromptAdapter(
        browser_lifecycle=lifecycle,
        browser_navigation=navigation,
        browser_diagnostics=diag,
        injector=PromptInjector(),
        sender=SendDispatcher(),
        streamer=StreamMonitor(),
        saver=Saver(),
        observability=ObservabilitySetup(
            cfg.log_path,
            StatusFileWriter(status_path_for(cfg.log_path)),
            MetricsCounter(metrics_path=cfg.log_path / "metrics.json"),
        ),
        flow=PromptFlowDispatcher(),
    )


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """Absolute path to tests/fixtures/ — single source of truth for all paths."""
    return FIXTURE_ROOT


@pytest.fixture
def cfg(fixture_root: Path, tmp_path: Path, reset_fixture_state) -> AppConfig:
    fx_input = fixture_root / "input"
    fx_output = fixture_root / "output"
    return AppConfig(
        mode="batch",
        input_path=fx_input,
        output_path=fx_output,
        session_path=fixture_root / "qwen_session",
        log_path=tmp_path / "log",
        headless=True,
    )


@pytest.fixture
def run_ctx() -> RunContext:
    return RunContext()


@pytest.fixture(autouse=True)
def reset_fixture_state(fixture_root: Path):
    restore_fixture_state(fixture_root)
    yield
    restore_fixture_state(fixture_root)


@pytest.fixture
def e2e_cfg(fixture_root: Path, reset_fixture_state) -> AppConfig:
    fx_input = fixture_root / "input"
    fx_output = fixture_root / "output"
    target_file = fx_input / "role-architect" / "todo" / "task_001.md"
    return AppConfig(
        mode="single",
        input_path=target_file if target_file.exists() else fx_input,
        output_path=fx_output,
        session_path=fixture_root / "qwen_session",
        log_path=fixture_root / "log",
        headless=True,
        timeout=300,
    )
