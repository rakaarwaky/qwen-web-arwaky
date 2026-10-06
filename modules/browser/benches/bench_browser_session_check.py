"""Benchmark for the browser session probe.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. The probe runs against a stub page, so the
benchmark needs no browser build and no network.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from modules.browser.src.capabilities_browser_adapter import SessionCheck
from modules.shared.src.taxonomy_core_constant import TEXTAREA_SELECTOR

pytestmark = pytest.mark.benchmark


def _ready_page() -> MagicMock:
    """Return a page stub that reads as a complete, usable chat."""
    page = MagicMock()
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    return page


def bench_session_check_is_alive(iterations: int = 2000) -> float:
    """Benchmark one readiness probe against a ready page."""
    checker = SessionCheck(_ready_page())
    page = checker.page

    start = time.perf_counter()
    for _ in range(iterations):
        page.evaluate.return_value = "complete"
        page.query_selector.return_value = MagicMock()
        checker.is_alive()
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_session_check_is_alive() -> None:
    """Report benchmark results for the readiness probe."""
    micros = bench_session_check_is_alive()
    print(f"\n[BENCHMARK] session_check.is_alive: {micros:.2f} µs/call")
    assert micros > 0


def test_bench_session_check_matches_one_selector() -> None:
    """Report the selector cost the probe pays on every poll."""
    page = _ready_page()
    start = time.perf_counter()
    for _ in range(2000):
        page.query_selector(TEXTAREA_SELECTOR)
    elapsed = time.perf_counter() - start
    micros = elapsed / 2000 * 1_000_000
    print(f"\n[BENCHMARK] query_selector: {micros:.2f} µs/call")
    assert micros > 0
