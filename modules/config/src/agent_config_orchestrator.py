"""Agent: build runtime configuration for every feature orchestrator.

Eight call sites used to import ``build_app_config`` directly, which put
the sandbox probe and the request-timeout environment override behind a
module-level import no test could substitute. This orchestrator takes
the four config capabilities as seams, so the environment-derived policy
has one owner and a test can substitute any of the four probes without
patching a module global.
"""

from __future__ import annotations

from modules.config.src.utility_config_app_factory import build_app_config
from modules.shared.src.contract_config_aggregate import IConfigAggregate
from modules.shared.src.contract_config_protocol import (
    IConfigCapacityProtocol,
    IConfigEnvironmentProtocol,
    IConfigPathResolverProtocol,
    IConfigSlotPlanProtocol,
    IConfigValidatorProtocol,
)
from modules.shared.src.taxonomy_config_vo import ConfigRequest, ConfigResponse
from modules.shared.src.taxonomy_core_vo import AppConfig, SlotRunPlan

__all__ = ["ConfigOrchestrator"]


class ConfigOrchestrator(IConfigAggregate):
    """Build ``AppConfig`` values on behalf of the other orchestrators.

    The sandbox verdict, the request-timeout ceiling, and the worker
    counts all come from the injected environment probe rather than from
    a module-level read, so a caller obtains a config that honors the
    operator's environment and a test can control that environment
    through the seam instead of a global patch.
    """

    def __init__(
        self,
        environment: IConfigEnvironmentProtocol,
        validator: IConfigValidatorProtocol,
        path_resolver: IConfigPathResolverProtocol,
        capacity: IConfigCapacityProtocol,
        slot_plan: IConfigSlotPlanProtocol,
    ) -> None:
        """Bind the five config capability seams.

        All five are required: a config built without the environment
        probe would silently ignore ``QWEN_DISABLE_SANDBOX``, one without
        the validator would skip the path checks that keep a run from
        spending a browser on an unwritable output, and one without the
        slot plan would leave each TUI form re-deriving its own output
        naming rule.
        """
        self._environment = environment
        self._validator = validator
        self._path_resolver = path_resolver
        self._capacity = capacity
        self._slot_plan = slot_plan

    # ─── Block 2: Aggregate Method Implementation ──────────

    def execute(self, request: ConfigRequest) -> ConfigResponse:
        """Run the requested config verb and return one response shape.

        A verb that cannot be answered reports the reason on the
        response rather than raising, so a surface renders the message
        without a try/except around every config call.
        """
        if request.verb == "for_mode":
            return ConfigResponse(
                config=self._build_config(request),
                timeout_sec=self._environment.request_timeout_sec(),
            )
        if request.verb == "sandbox_report":
            return ConfigResponse(sandbox=self._environment.sandbox_report())
        if request.verb == "capacity":
            return ConfigResponse(capacity=self._capacity.report())
        if request.verb == "slot_plan":
            resolved = self._slot_plan.resolve_slot_run_plan(
                request.prompt_val,
                request.file_val,
                request.output_val,
                request.headless,
            )
            if isinstance(resolved, SlotRunPlan):
                return ConfigResponse(config=resolved)
            return ConfigResponse(error=resolved.message)
        return ConfigResponse(error=f"Unknown config verb: {request.verb!r}")

    # ─── Block 3: Dunder Methods, Factories & Helpers ──────

    def _build_config(self, request: ConfigRequest) -> AppConfig:
        """Build the ``AppConfig`` a *request* describes.

        The sandbox verdict from the environment probe is applied on top
        of the factory's own probe, so a forced-sandbox host that reports
        no seccomp filter still launches sandboxed when the operator
        asked for it.
        """
        sandbox = self._environment.sandbox_report()
        return build_app_config(
            str(request.mode),
            input_path=request.input_path,
            output_path=request.output_path,
            headless=bool(request.headless),
            request_timeout=int(self._environment.request_timeout_sec()),
            disable_sandbox=sandbox.state in ("disabled_by_env", "disabled_by_host"),
        )
