"""Benchmark for stream monitor response detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.core.src.capabilities_stream_monitor import StreamMonitor


def test_is_generation_complete_bench(benchmark):
    """Benchmark generation completion detection speed."""
    monitor = StreamMonitor()
    page = MagicMock()

    # Mock page.evaluate returning generation state
    page.evaluate.side_effect = [
        True,   # first call - generation active
        False,  # second call - generation ended
    ]

    results = []

    def run():
        result = monitor.is_generation_complete(page)
        results.append(result)

    benchmark(run)
    assert False in results  # should detect when generation ends


def test_is_thinking_active_bench(benchmark):
    """Benchmark thinking card detection speed."""
    monitor = StreamMonitor()
    page = MagicMock()

    # Mock page.evaluate for thinking state
    page.evaluate.side_effect = [
        True,   # thinking active
        False,  # thinking ended
    ]

    results = []

    def run():
        result = monitor.is_thinking_active(page)
        results.append(result)

    benchmark(run)
    assert False in results  # should detect when thinking ends

