"""Root: single DI container for CLI and MCP features.

Wires the 5 specialized agent orchestrators with capability implementations.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
from modules.cli.src.capabilities_slot_plan_resolver import SlotRunPlanResolver

# Root is the composition layer, so it wires the functional doctor gate into
# the updater: after an upgrade the pipeline re-runs the operator diagnostics
# and rolls back when they fail (issue #294). The gate itself lives in the
# doctor Surface; Capabilities only ever sees an injected callable.
from modules.cli.src.surface_cli_doctor_command import build_smoke_gate

# agent_job_orchestrator
from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_folder_compiler import FolderCompiler
from modules.jobs.src.capabilities_folder_to_attachment import FolderToAttachmentAdapter
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.prompt.src.agent_shared_flow_orchestrator import SharedFlowOrchestrator

# capabilities_attachment_prompt_adapter
from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter

# capabilities_direct_prompt_adapter
from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter
from modules.prompt.src.capabilities_file_uploader import FileUploader
from modules.prompt.src.capabilities_output_saver import Saver

# capabilities_prompt_file_adapter
from modules.prompt.src.capabilities_prompt_file_adapter import PromptFileAdapter
from modules.prompt.src.capabilities_prompt_injector import PromptInjector
from modules.prompt.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt.src.capabilities_stream_monitor import StreamMonitor

# agent_session_orchestrator
from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
from modules.session.src.capabilities_session_manager import SessionManager

# capabilities_setup_adapter
from modules.session.src.capabilities_setup_adapter import SetupAdapter
from modules.session.src.capabilities_swarm_adapter import SwarmAdapter
from modules.session.src.capabilities_workspace_provisioner import WorkspaceProvisioner
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    IPromptFlowAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import ISlotRunPlanProtocol, IUpdateProtocol
from modules.shared.src.contract_session_aggregate import ISessionManagerProtocol, ISessionRotatorAggregate
from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_JOBS_DIR,
    DEFAULT_LOG,
    SWARM_CONCURRENCY_ENV,
)
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec
from modules.shared.src.utility_core_capacity import recommended_max_workers
from modules.shared.src.utility_core_status import status_path_for
from modules.update.src.capabilities_update_manager import UpdateManager


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
            env_workers = os.environ.get("QWEN_WEB_MAX_WORKERS")
            max_workers = int(env_workers) if env_workers and env_workers.isdigit() else recommended_max_workers()

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
        self.observability = ObservabilitySetup(
            log,
            status_writer=StatusFileWriter(status_path_for(log)),
            metrics=MetricsCounter(metrics_path=log / "metrics.json"),
        )
        self.workspace = WorkspaceProvisioner()
        self.updater: IUpdateProtocol = UpdateManager(smoke_gate=build_smoke_gate())
        self.folder_compiler = FolderCompiler()
        self.folder_adapter = FolderToAttachmentAdapter(folder_compiler=self.folder_compiler)
        # AR-1: TUI slot-config resolver exposed via the Root container so the
        # Surface (QwenTuiApp) can consume it through ISlotRunPlanProtocol
        # instead of importing the Capabilities class directly.
        self.slot_plan: ISlotRunPlanProtocol = SlotRunPlanResolver()

        # Shared prompt-flow agent (injected into the three prompt orchestrators)
        self.agent_shared_flow_orchestrator: IPromptFlowAggregate = SharedFlowOrchestrator()

        # Shared targeted-cancel registry (injected into the prompt file / attachment orchestrators)
        self.run_cancel_registry: CapabilitiesRunCancelRegistry = CapabilitiesRunCancelRegistry()

        # The 5 specialized agent orchestrators
        self.agent_direct_prompt_orchestrator: IDirectPromptAggregate = DirectPromptAdapter(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.agent_shared_flow_orchestrator,
        )
        self.agent_prompt_file_orchestrator: IPromptFileAggregate = PromptFileAdapter(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.agent_shared_flow_orchestrator,
            cancel=self.run_cancel_registry,
        )
        self.agent_attachment_prompt_orchestrator: IAttachmentPromptAggregate = AttachmentPromptAdapter(
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
        from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter

        self.session_rotator: ISessionRotatorAggregate = SessionRotationAdapter(
            session_manager=self.session_manager,
            health_checker=self.session_health_checker,
        )
        self.agent_setup_orchestrator: ISetupAggregate = SetupAdapter(
            browser=self.browser,
            observability=self.observability,
        )
        DEFAULT_JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.job_storage = JobStorage(storage_dir=DEFAULT_JOBS_DIR)
        self.agent_job_orchestrator: IJobManagerAggregate = AgentJobOrchestrator(
            storage=self.job_storage,
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
        # Issue #277: the Swarm fan-out must respect the same shared resource
        # guards as the job pipeline — the shared breaker and limiter are
        # injected so 10 concurrent agent attempts cannot bypass them.
        self.agent_swarm_orchestrator: ISwarmAggregate = SwarmAdapter(
            attachment=self.agent_attachment_prompt_orchestrator,
            folder_adapter=self.folder_adapter,
            browser_concurrency=swarm_workers,
            headless=swarm_headless,
            circuit_breaker=self.cb,
            rate_limiter=self.rl,
        )

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
