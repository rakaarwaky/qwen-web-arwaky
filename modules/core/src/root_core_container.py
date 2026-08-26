"""Root: single DI container for CLI and MCP features.

Wires the 5 specialized agent orchestrators with capability implementations.
"""

from __future__ import annotations

from pathlib import Path

# agent_attachment_prompt_orchestrator
from modules.core.src.agent_attachment_prompt_orchestrator import AttachmentPromptOrchestrator

# agent_direct_prompt_orchestrator
from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator

# agent_job_orchestrator
from modules.core.src.agent_job_orchestrator import AgentJobOrchestrator

# agent_prompt_file_orchestrator
from modules.core.src.agent_prompt_file_orchestrator import PromptFileOrchestrator

# agent_session_orchestrator
from modules.core.src.agent_session_orchestrator import SessionOrchestrator

# agent_setup_orchestrator
from modules.core.src.agent_setup_orchestrator import SetupOrchestrator
from modules.core.src.agent_shared_flow_orchestrator import SharedFlowOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_job_manager import JobManager
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.core.src.capabilities_update_manager import UpdateManager
from modules.core.src.capabilities_workspace_provisioner import WorkspaceProvisioner
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    IPromptFlowAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec


class SharedContainer:
    """Single dependency injection container shared by CLI and MCP features."""

    def __init__(
        self,
        log_path: Path | str | None = None,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_window: int = 30,
        rate_limit_per_minute: int = 60,
    ) -> None:
        log = Path(log_path) if log_path else DEFAULT_LOG

        self.cb = CircuitBreaker(
            FailureThreshold(circuit_breaker_threshold),
            WindowSec(circuit_breaker_window),
        )
        self.rl = RateLimiter(MaxPerMinute(rate_limit_per_minute))

        self.browser = BrowserAdapter()
        self.injector = PromptInjector()
        self.sender = SendDispatcher()
        self.streamer = StreamMonitor()
        self.uploader = FileUploader()
        self.saver = Saver()
        self.observability = ObservabilitySetup(log)
        self.workspace = WorkspaceProvisioner()
        self.updater: IUpdateProtocol = UpdateManager()

        # Shared prompt-flow agent (injected into the three prompt orchestrators)
        self.agent_shared_flow_orchestrator: IPromptFlowAggregate = SharedFlowOrchestrator()

        # The 5 specialized agent orchestrators
        self.agent_direct_prompt_orchestrator: IDirectPromptAggregate = DirectPromptOrchestrator(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.agent_shared_flow_orchestrator,
        )
        self.agent_prompt_file_orchestrator: IPromptFileAggregate = PromptFileOrchestrator(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.agent_shared_flow_orchestrator,
        )
        self.agent_attachment_prompt_orchestrator: IAttachmentPromptAggregate = AttachmentPromptOrchestrator(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            uploader=self.uploader,
            saver=self.saver,
            observability=self.observability,
            flow=self.agent_shared_flow_orchestrator,
        )
        self.agent_session_orchestrator: ISessionAggregate = SessionOrchestrator(
            browser=self.browser,
            observability=self.observability,
        )
        self.agent_setup_orchestrator: ISetupAggregate = SetupOrchestrator(
            browser=self.browser,
            observability=self.observability,
        )
        self.job_manager = JobManager()
        self.agent_job_orchestrator: IJobManagerAggregate = AgentJobOrchestrator(
            storage=self.job_manager,
            file_only=self.agent_prompt_file_orchestrator,
            attachment=self.agent_attachment_prompt_orchestrator,
        )

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
