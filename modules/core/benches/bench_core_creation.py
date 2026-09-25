"""Benchmark tests for core module — performance measurement using pytest-benchmark."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


@pytest.mark.benchmark
class TestCoreBenchmarks:
    """Benchmark tests for core module performance."""

    def test_orchestrator_creation_benchmark(self, benchmark):
        """Benchmark DirectPromptOrchestrator instantiation."""
        from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator

        def setup():
            browser = MagicMock()
            injector = MagicMock()
            sender = MagicMock()
            streamer = MagicMock()
            saver = MagicMock()
            observability = MagicMock()
            observability.get_logger.return_value = MagicMock()
            return DirectPromptOrchestrator(
                browser=browser, injector=injector, sender=sender,
                streamer=streamer, saver=saver, observability=observability, flow=MagicMock()
            )

        benchmark(setup)

    def test_prompt_injector_creation_benchmark(self, benchmark):
        """Benchmark PromptInjector instantiation."""
        from modules.core.src.capabilities_prompt_injector import PromptInjector

        benchmark(PromptInjector)

    def test_stream_monitor_creation_benchmark(self, benchmark):
        """Benchmark StreamMonitor instantiation."""
        from modules.core.src.capabilities_stream_monitor import StreamMonitor

        benchmark(StreamMonitor)

    def test_send_dispatcher_creation_benchmark(self, benchmark):
        """Benchmark SendDispatcher instantiation."""
        from modules.core.src.capabilities_send_dispatcher import SendDispatcher

        benchmark(SendDispatcher)
