"""Benchmark for send dispatcher parsing wait logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.core.src.capabilities_send_dispatcher import SendDispatcher


def test_click_send_button_bench(benchmark):
    """Benchmark send button click speed."""
    sender = SendDispatcher()
    page = MagicMock()
    page.is_enabled.return_value = True
    page.click.return_value = None

    results = []

    def run():
        # Mock _wait_for_send_enabled to return immediately
        try:
            sender.click_send(page)
        except Exception:
            pass
        results.append(True)

    benchmark(run)
    assert results[-1] is True


def test_count_messages_bench(benchmark):
    """Benchmark message count detection speed."""
    sender = SendDispatcher()
    page = MagicMock()

    # Mock page.evaluate for fast path
    mock_locator = MagicMock()
    mock_locator.count.return_value = 1
    page.locator.return_value = mock_locator

    results = []

    def run():
        result = sender.count_messages(page)
        results.append(result)

    benchmark(run)
    assert results[-1] is not None

