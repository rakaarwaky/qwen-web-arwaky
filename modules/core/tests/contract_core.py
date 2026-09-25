"""Contract tests for core module — verifies protocol/aggregate implementations."""

from __future__ import annotations

import pytest

from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_stream_monitor import StreamMonitor


class TestCoreContracts:
    """Verify core module contract implementations exist and are valid."""

    def test_direct_prompt_orchestrator_instantiation(self):
        from unittest.mock import MagicMock
        browser = MagicMock()
        injector = MagicMock()
        sender = MagicMock()
        streamer = MagicMock()
        saver = MagicMock()
        observability = MagicMock()
        observability.get_logger.return_value = MagicMock()
        orchestrator = DirectPromptOrchestrator(
            browser=browser, injector=injector, sender=sender,
            streamer=streamer, saver=saver, observability=observability, flow=MagicMock()
        )
        assert orchestrator is not None

    def test_browser_adapter_exists(self):
        assert hasattr(BrowserAdapter, "wait_for_element")

    def test_send_dispatcher_exists(self):
        assert hasattr(SendDispatcher, "send_prompt")

    def test_stream_monitor_exists(self):
        assert hasattr(StreamMonitor, "monitor_stream")

    def test_orchestrator_has_process_method(self):
        from unittest.mock import MagicMock
        browser = MagicMock()
        injector = MagicMock()
        sender = MagicMock()
        streamer = MagicMock()
        saver = MagicMock()
        observability = MagicMock()
        observability.get_logger.return_value = MagicMock()
        orchestrator = DirectPromptOrchestrator(
            browser=browser, injector=injector, sender=sender,
            streamer=streamer, saver=saver, observability=observability, flow=MagicMock()
        )
        assert hasattr(orchestrator, "process_direct_prompt")
