"""Benchmark for send dispatcher operations.

Uses time.perf_counter for measuring performance without requiring pytest-benchmark plugin.
"""

from __future__ import annotations

import contextlib
import time
from unittest.mock import MagicMock

from modules.core.src.capabilities_send_dispatcher import SendDispatcher


def bench_click_send(iterations: int = 1000) -> float:
    """Benchmark send button click speed."""
    sender = SendDispatcher()
    page = MagicMock()
    page.is_enabled.return_value = True
    page.click.return_value = None

    start = time.perf_counter()
    for _ in range(iterations):
        with contextlib.suppress(Exception):
            sender.click_send(page)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def bench_count_messages(iterations: int = 1000) -> float:
    """Benchmark message count detection."""
    sender = SendDispatcher()
    page = MagicMock()

    mock_locator = MagicMock()
    mock_locator.count.return_value = 1
    page.locator.return_value = mock_locator

    start = time.perf_counter()
    for _ in range(iterations):
        mock_locator.count.return_value = 1
        _ = sender.count_messages(page)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def test_bench_click_send():
    """Report benchmark results for click_send."""
    micros = bench_click_send()
    print(f"\n[BENCHMARK] click_send: {micros:.2f} µs/call")
    assert micros > 0


def test_bench_count_messages():
    """Report benchmark results for count_messages."""
    micros = bench_count_messages()
    print(f"\n[BENCHMARK] count_messages: {micros:.2f} µs/call")
    assert micros > 0
