"""Benchmark for stream monitor response detection.

Uses time.perf_counter for measuring performance without requiring pytest-benchmark plugin.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from modules.core.src.capabilities_stream_monitor import StreamMonitor


def bench_is_generation_complete(iterations: int = 1000) -> float:
    """Benchmark generation completion detection."""
    monitor = StreamMonitor()
    page = MagicMock()
    page.evaluate.side_effect = [True, False]

    start = time.perf_counter()
    for _ in range(iterations):
        page.evaluate.reset_mock()
        page.evaluate.side_effect = [True, False]
        _ = monitor.is_generation_complete(page)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def bench_is_thinking_active(iterations: int = 1000) -> float:
    """Benchmark thinking card detection."""
    monitor = StreamMonitor()
    page = MagicMock()
    page.evaluate.side_effect = [True, False]

    start = time.perf_counter()
    for _ in range(iterations):
        page.evaluate.reset_mock()
        page.evaluate.side_effect = [True, False]
        _ = monitor.is_thinking_active(page)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def test_bench_is_generation_complete():
    """Report benchmark results for generation detection."""
    micros = bench_is_generation_complete()
    print(f"\n[BENCHMARK] is_generation_complete: {micros:.2f} µs/call")
    assert micros > 0


def test_bench_is_thinking_active():
    """Report benchmark results for thinking detection."""
    micros = bench_is_thinking_active()
    print(f"\n[BENCHMARK] is_thinking_active: {micros:.2f} µs/call")
    assert micros > 0
