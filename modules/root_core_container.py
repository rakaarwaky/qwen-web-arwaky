"""Root: single DI container for CLI and MCP features.

Wires the 5 specialized agent orchestrators with capability implementations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from modules.browser.src.agent_browser_orchestrator import BrowserOrchestrator
from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics
from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.browser.src.capabilities_browser_navigation import BrowserNavigation
from modules.browser.src.capabilities_browser_session_check import SessionCheck

# agent_config_orchestrator
from modules.config.src.agent_config_orchestrator import ConfigOrchestrator
from modules.config.src.capabilities_config_capacity import ConfigCapacityAdvisor
from modules.config.src.capabilities_config_environment import ConfigEnvironment

# Root is the composition layer, so it wires the functional doctor gate into
# the updater: after an upgrade the pipeline re-runs the operator diagnostics
# and rolls back when they fail (issue #294). The gate factory lives in the
# Capabilities layer; the update pipeline sees only an injected callable.
from modules.config.src.capabilities_config_health_probe import build_smoke_gate
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.config.src.capabilities_config_validator import ConfigValidator

# agent_session_orchestrator
# SessionOrchestrator is the single agent in the session feature folder; it
# implements ISessionAggregate (validate/delete/login) for the whole
# session feature, so the setup-labelled surfaces reuse
# ``agent_session_orchestrator``.
from modules.config.src.capabilities_workspace_provisioner import WorkspaceProvisioner

# agent_job_orchestrator
from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_folder_compiler import FolderCompiler
from modules.jobs.src.capabilities_folder_to_attachment import FolderToAttachmentAdapter
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.jobs.src.capabilities_status_writer import StatusFileWriter

# agent_logging_orchestrator
from modules.logging.src.agent_logging_orchestrator import LoggingOrchestrator
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup

# capabilities_attachment_prompt_adapter
from modules.prompt.src.agent_prompt_orchestrator import PromptOrchestrator
from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter

# capabilities_direct_prompt_adapter
from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter
from modules.prompt.src.capabilities_file_uploader import FileUploader
from modules.prompt.src.capabilities_output_saver import Saver

# capabilities_prompt_file_adapter
from modules.prompt.src.capabilities_prompt_file_adapter import PromptFileAdapter
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.prompt.src.capabilities_prompt_injector import PromptInjector
from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.prompt.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt.src.capabilities_stream_monitor import StreamMonitor
from modules.session.src.agent_session_orchestrator import SessionOrchestrator
from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
from modules.session.src.capabilities_session_manager import SessionManager
from modules.session.src.capabilities_session_profile_preparer import ProfilePreparer
from modules.session.src.capabilities_session_renewal import SessionRenewer
from modules.shared.src.browser.contract_browser_aggregate import IBrowserAggregate
from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserDiagnosticsProtocol,
    IBrowserLifecycleProtocol,
    IBrowserModelPolicyProtocol,
    IBrowserNavigationProtocol,
)
from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_JOBS_DIR,
    DEFAULT_LOG,
    DEFAULT_PACKAGE_NAME,
    SWARM_CONCURRENCY_ENV,
    SWARM_OUTPUT_ROOT,
)
from modules.shared.src.common.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.common.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec
from modules.shared.src.common.utility_core_capacity import recommended_max_workers
from modules.shared.src.common.utility_core_status import status_path_for
from modules.shared.src.config.contract_config_aggregate import IConfigAggregate
from modules.shared.src.config.contract_config_protocol import IConfigSlotPlanProtocol
from modules.shared.src.jobs.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.logging.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.contract_prompt_protocol import (
    IAttachmentPromptProtocol,
    IDirectPromptProtocol,
    IPromptFileProtocol,
    IPromptFlowProtocol,
)
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.contract_session_protocol import (
    ISessionManagerProtocol,
    ISessionRenewalProtocol,
    ISessionRotatorProtocol,
)
from modules.shared.src.swarm.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.update.contract_update_aggregate import IUpdateAggregate
from modules.shared.src.update.contract_update_protocol import (
    IUpdateCheckProtocol,
    IUpdateRollbackProtocol,
    IUpdateUpgradeProtocol,
    IUpdateVerifyProtocol,
)
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_cancel import SwarmCancelRunner
from modules.swarm.src.capabilities_swarm_progress import SwarmProgressRunner
from modules.swarm.src.capabilities_swarm_registry import SwarmRegistry
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner
from modules.update.src.agent_update_orchestrator import UpdateOrchestrator
from modules.update.src.capabilities_update_check import UpdateCheckCapability
from modules.update.src.capabilities_update_rollback import UpdateRollbackCapability
from modules.update.src.capabilities_update_upgrade import UpdateUpgradeCapability
from modules.update.src.capabilities_update_verify import UpdateVerifyCapability


def _new_browser_model_policy() -> IBrowserModelPolicyProtocol:
    """Construct the browser model-policy capability (AES503 wiring helper)."""
    from modules.browser.src.capabilities_browser_model_policy import BrowserModelPolicy

    return BrowserModelPolicy()


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

        # Browser model-policy capability: owns the issue #283/#374 model
        # selection/verification fallback rules; the container owns the seam
        # and injects the same instance into the adapter so the adapter's
        # model steps delegate to a shared capability (the adapter file
        # itself never imports a sibling capability, AES201).
        self.browser_model_policy = _new_browser_model_policy()
        self.browser = BrowserAdapter(model_policy=self.browser_model_policy)
        # Narrow browser views: each capability implements exactly one split
        # protocol and delegates to the facade (AES201: a capability never
        # imports a sibling capability; the container wires the adapter into
        # both views so every view drives one Chromium process group).
        self.browser_lifecycle: IBrowserLifecycleProtocol = BrowserLifecycle(self.browser)
        self.browser_navigation: IBrowserNavigationProtocol = BrowserNavigation(self.browser)
        self.browser_diagnostics: IBrowserDiagnosticsProtocol = BrowserDiagnostics(self.browser)
        # Browser capability: the session probe (page liveness + auth
        # assertion) the adapter delegates to; registered here so the
        # container owns the seam.
        self.session_check = SessionCheck
        self.injector = PromptInjector()
        self.sender = SendDispatcher()
        self.streamer = StreamMonitor()
        self.uploader = FileUploader()
        self.saver = Saver()
        self.metrics = MetricsCounter(metrics_path=log / "metrics.json")
        self.observability = ObservabilitySetup(
            log,
            status_writer=StatusFileWriter(status_path_for(log)),
            metrics=self.metrics,
        )
        self.workspace = WorkspaceProvisioner()
        self.session_manager: ISessionManagerProtocol = SessionManager()
        self.profile_preparer: ProfilePreparer = ProfilePreparer()
        # Session infrastructure (health checker + renewer) is composed here;
        # the rotator and session aggregate follow later after the prompt adapters.
        self.session_health_checker = SessionHealthChecker(browser_lifecycle=self.browser_lifecycle)
        self.session_renewer: ISessionRenewalProtocol = SessionRenewer(
            browser_lifecycle=self.browser_lifecycle,
            observability=self.observability,
        )
        self.updater_check: IUpdateCheckProtocol = UpdateCheckCapability(DEFAULT_PACKAGE_NAME)
        self.updater_upgrade: IUpdateUpgradeProtocol = UpdateUpgradeCapability(DEFAULT_PACKAGE_NAME)
        self.updater_rollback: IUpdateRollbackProtocol = UpdateRollbackCapability(
            self.updater_upgrade,
            package_name=DEFAULT_PACKAGE_NAME,
        )
        # Feature agents sit between capabilities and surfaces so no caller
        # repeats the sequencing each feature owns.
        self.agent_browser_orchestrator: IBrowserAggregate = BrowserOrchestrator(self.browser, self.observability)
        self.agent_logging_orchestrator: IObservabilityAggregate = LoggingOrchestrator(self.observability, self.metrics)
        self.folder_compiler = FolderCompiler()
        self.folder_adapter = FolderToAttachmentAdapter(folder_compiler=self.folder_compiler)
        # AR-1: TUI slot-config resolver exposed via the Root container so the
        # Surface (QwenTuiApp) can consume it through IConfigSlotPlanProtocol
        # instead of importing the Capabilities class directly.
        self.slot_plan: IConfigSlotPlanProtocol = SlotRunPlanResolver()

        # AR-2: the config feature reaches Surfaces and sibling orchestrators
        # as one aggregate, so every AppConfig a caller receives went through
        # the same sandbox probe and the same timeout ceiling. The five
        # capabilities stay injectable seams for tests that need to steer
        # the environment or the host-capacity verdict.
        self.config: IConfigAggregate = ConfigOrchestrator(
            environment=ConfigEnvironment(),
            validator=ConfigValidator(),
            path_resolver=ConfigPathResolver(),
            capacity=ConfigCapacityAdvisor(),
            slot_plan=self.slot_plan,
            workspace=self.workspace,
        )

        # Shared prompt-flow capability (injected into the three prompt adapters)
        self.prompt_flow_dispatcher: IPromptFlowProtocol = PromptFlowDispatcher()

        # Shared targeted-cancel registry (injected into the prompt file / attachment orchestrators)
        self.run_cancel_registry: CapabilitiesRunCancelRegistry = CapabilitiesRunCancelRegistry()

        # The 5 specialized agent orchestrators
        self.agent_direct_prompt_orchestrator: IDirectPromptProtocol = DirectPromptAdapter(
            browser_lifecycle=self.browser_lifecycle,
            browser_navigation=self.browser_navigation,
            browser_diagnostics=self.browser_diagnostics,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.prompt_flow_dispatcher,
        )
        self.agent_prompt_file_orchestrator: IPromptFileProtocol = PromptFileAdapter(
            browser_lifecycle=self.browser_lifecycle,
            browser_navigation=self.browser_navigation,
            browser_diagnostics=self.browser_diagnostics,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            saver=self.saver,
            observability=self.observability,
            flow=self.prompt_flow_dispatcher,
            cancel=self.run_cancel_registry,
        )
        self.agent_attachment_prompt_orchestrator: IAttachmentPromptProtocol = AttachmentPromptAdapter(
            browser_lifecycle=self.browser_lifecycle,
            browser_navigation=self.browser_navigation,
            browser_diagnostics=self.browser_diagnostics,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            uploader=self.uploader,
            saver=self.saver,
            observability=self.observability,
            flow=self.prompt_flow_dispatcher,
            folder_adapter=self.folder_adapter,
            cancel=self.run_cancel_registry,
        )
        # Shared prompt aggregate: the three adapters are composed first,
        # then PromptOrchestrator wires them into a single IPromptAggregate.
        self.prompt_aggregate: IPromptAggregate = PromptOrchestrator(
            direct=self.agent_direct_prompt_orchestrator,
            file_only=self.agent_prompt_file_orchestrator,
            attachment=self.agent_attachment_prompt_orchestrator,
            cancel_registry=self.run_cancel_registry,
            observability=self.observability,
        )
        # Session rotation: the rotator needs the prompt aggregate so that
        # execute_with_rotation can delegate real work instead of using a
        # simulated response (ARCH-2-003).
        from modules.session.src.capabilities_session_rotation_adapter import SessionRotationAdapter

        self.session_rotator: ISessionRotatorProtocol = SessionRotationAdapter(
            session_manager=self.session_manager,
            health_checker=self.session_health_checker,
            prompt=self.prompt_aggregate,
        )
        self.agent_session_orchestrator: ISessionAggregate = SessionOrchestrator(
            browser=self.browser,
            observability=self.observability,
            sessions=self.session_manager,
            renewer=self.session_renewer,
            health_checker=self.session_health_checker,
            rotator=self.session_rotator,
        )
        # updater_verify and the update aggregate depend on the session orchestrator
        # (smoke gate) so they are composed after it.
        self.updater_verify: IUpdateVerifyProtocol = UpdateVerifyCapability(
            self.updater_check,
            self.updater_upgrade,
            self.updater_rollback,
            package_name=DEFAULT_PACKAGE_NAME,
            smoke_gate=build_smoke_gate(self.agent_session_orchestrator),
        )
        self.agent_update_orchestrator: IUpdateAggregate = UpdateOrchestrator(
            self.updater_check,
            self.updater_upgrade,
            self.updater_verify,
            self.updater_rollback,
            self.observability,
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
        #
        # One registry backs all three Swarm seams: the capability files
        # never import each other, so the shared fan-out state is reached
        # through the single store composed here.
        swarm_registry = SwarmRegistry()
        swarm_attachment = cast(IPromptAggregate, self.agent_attachment_prompt_orchestrator)
        self.swarm_registry: SwarmRegistry = swarm_registry
        self.agent_swarm_orchestrator: ISwarmAggregate = SwarmOrchestrator(
            SwarmRunner(
                attachment=swarm_attachment,
                registry=swarm_registry,
                output_root=SWARM_OUTPUT_ROOT,
                browser_concurrency=swarm_workers,
                headless=swarm_headless,
                circuit_breaker=self.cb,
                rate_limiter=self.rl,
            ),
            SwarmProgressRunner(registry=swarm_registry),
            SwarmCancelRunner(
                registry=swarm_registry,
                attachment=swarm_attachment,
            ),
            self.observability,
            folder_adapter=self.folder_adapter,
        )

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
