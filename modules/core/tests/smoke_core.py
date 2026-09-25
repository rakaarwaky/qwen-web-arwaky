"""Smoke tests for core module — fast verification that core orchestrators and capabilities work."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestCoreSmoke:
    """Fast smoke tests for core module (must complete in <5s)."""

    def test_direct_prompt_orchestrator_creates(self):
        from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
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

    def test_browser_adapter_instantiation(self):
        from modules.core.src.capabilities_browser_adapter import BrowserAdapter
        adapter = BrowserAdapter()
        assert adapter is not None

    def test_send_dispatcher_instantiation(self):
        from modules.core.src.capabilities_send_dispatcher import SendDispatcher
        dispatcher = SendDispatcher()
        assert dispatcher is not None

    def test_stream_monitor_instantiation(self):
        from modules.core.src.capabilities_stream_monitor import StreamMonitor
        monitor = StreamMonitor()
        assert monitor is not None

    def test_prompt_injector_instantiation(self):
        from modules.core.src.capabilities_prompt_injector import PromptInjector
        injector = PromptInjector()
        assert injector is not None

    def test_output_saver_instantiation(self):
        from modules.core.src.capabilities_output_saver import Saver
        saver = Saver()
        assert saver is not None

    def test_job_manager_instantiation(self):
        from modules.core.src.capabilities_job_manager import JobManager
        manager = JobManager()
        assert manager is not None
