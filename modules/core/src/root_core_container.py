"""Root: single DI container for CLI and MCP features.

Wires the 5 specialized agent orchestrators with capability implementations.
"""

from __future__ import annotations

import os
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
from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_folder_compiler import FolderCompiler
from modules.core.src.capabilities_folder_to_attachment import FolderToAttachmentAdapter
from modules.core.src.capabilities_job_manager import JobManager
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_session_health_checker import SessionHealthChecker
from modules.core.src.capabilities_session_manager import SessionManager
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.core.src.capabilities_tui_slot_config import TuiSlotConfigResolver
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
from modules.shared.src.contract_core_protocol import ITuiSlotConfigProtocol, IUpdateProtocol
from modules.shared.src.contract_session_aggregate import ISessionManagerProtocol, ISessionRotatorAggregate
from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_JOBS_DIR,
    DEFAULT_LOG,
    DEFAULT_MAX_WORKERS,
    SWARM_CONCURRENCY_ENV,
)
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
        max_workers: int | None = None,
    ) -> None:
        log = Path(log_path) if log_path else DEFAULT_LOG
        if max_workers is None:
            max_workers = int(os.environ.get("QWEN_WEB_MAX_WORKERS", str(DEFAULT_MAX_WORKERS)))

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
        self.folder_compiler = FolderCompiler()
        self.folder_adapter = FolderToAttachmentAdapter(folder_compiler=self.folder_compiler)
        # AR-1: TUI slot-config resolver exposed via the Root container so the
        # Surface (QwenTuiApp) can consume it through ITuiSlotConfigProtocol
        # instead of importing the Capabilities class directly.
        self.tui_slot_config: ITuiSlotConfigProtocol = TuiSlotConfigResolver()

        # Shared prompt-flow agent (injected into the three prompt orchestrators)
        self.agent_shared_flow_orchestrator: IPromptFlowAggregate = SharedFlowOrchestrator()

        # Shared targeted-cancel registry (injected into the prompt file / attachment orchestrators)
        self.run_cancel_registry: CapabilitiesRunCancelRegistry = CapabilitiesRunCancelRegistry()

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
            cancel=self.run_cancel_registry,
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
            folder_adapter=self.folder_adapter,
            cancel=self.run_cancel_registry,
        )
        self.agent_session_orchestrator: ISessionAggregate = SessionOrchestrator(
            browser=self.browser,
            observability=self.observability,
        )

        # Session rotation infrastructure
        self.session_manager: ISessionManagerProtocol = SessionManager()
        self.session_health_checker = SessionHealthChecker()
        from modules.core.src.agent_session_rotation_orchestrator import SessionRotator

        self.session_rotator: ISessionRotatorAggregate = SessionRotator(
            session_manager=self.session_manager,
            health_checker=self.session_health_checker,
        )
        self.agent_setup_orchestrator: ISetupAggregate = SetupOrchestrator(
            browser=self.browser,
            observability=self.observability,
        )
        DEFAULT_JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.job_manager = JobManager(storage_dir=DEFAULT_JOBS_DIR)
        self.agent_job_orchestrator: IJobManagerAggregate = AgentJobOrchestrator(
            storage=self.job_manager,
            file_only=self.agent_prompt_file_orchestrator,
            attachment=self.agent_attachment_prompt_orchestrator,
            max_workers=max_workers,
            circuit_breaker=self.cb,
            rate_limiter=self.rl,
        )
        swarm_env = os.environ.get(SWARM_CONCURRENCY_ENV, "").strip()
        swarm_workers = int(swarm_env) if swarm_env.isdigit() and int(swarm_env) > 0 else max_workers
        swarm_headless_env = os.environ.get("QWA_SWARM_HEADLESS", "").strip()
        swarm_headless = swarm_headless_env != "0" and swarm_headless_env.casefold() != "false"
        self.agent_swarm_orchestrator: ISwarmAggregate = SwarmOrchestrator(
            attachment=self.agent_attachment_prompt_orchestrator,
            folder_adapter=self.folder_adapter,
            browser_concurrency=swarm_workers,
            headless=swarm_headless,
        )

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
