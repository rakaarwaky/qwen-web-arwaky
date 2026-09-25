"""Acceptance tests for core module — verifies business requirements are met."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


class TestCoreAcceptance:
    """Acceptance tests mapping to business requirements."""

    def test_orchestrator_can_be_instantiated_with_all_deps(self):
        """FRD-001: DirectPromptOrchestrator must accept all required dependencies."""
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
        assert orchestrator._browser is browser
        assert orchestrator._injector is injector
        assert orchestrator._sender is sender

    def test_capability_browser_adapter_exists(self):
        """FRD-002: BrowserAdapter capability must exist."""
        from modules.core.src.capabilities_browser_adapter import BrowserAdapter
        adapter = BrowserAdapter()
        assert adapter is not None

    def test_capability_send_dispatcher_exists(self):
        """FRD-003: SendDispatcher capability must exist."""
        from modules.core.src.capabilities_send_dispatcher import SendDispatcher
        dispatcher = SendDispatcher()
        assert dispatcher is not None

    def test_capability_stream_monitor_exists(self):
        """FRD-004: StreamMonitor capability must exist."""
        from modules.core.src.capabilities_stream_monitor import StreamMonitor
        monitor = StreamMonitor()
        assert monitor is not None

    def test_orchestrator_has_process_method(self):
        """FRD-005: DirectPromptOrchestrator must have a process method."""
        from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
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
        assert callable(orchestrator.process_direct_prompt)

    def test_output_saver_can_save_file(self, tmp_path: Path):
        """FRD-006: Saver must be able to save content to a file."""
        from modules.core.src.capabilities_output_saver import Saver
        from modules.shared.src import RunContext

        saver = Saver()
        ctx = RunContext(session_id="test")
        test_content = "# Test Output\n\nThis is a test."
        result = saver.save(str(tmp_path / "test.md"), test_content, ctx)
        assert result is not None
