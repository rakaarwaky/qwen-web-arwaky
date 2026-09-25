"""Integration tests for AR-1: TUI slot-config DI wiring (issue #316).

Locks the three-party chain TUI Surface → Root Container → Capabilities
(SlotRunPlanResolver): the container exposes the resolver as
ISlotRunPlanProtocol, and QwenTuiApp receives it through its constructor
— never by importing the capability directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.contract_core_protocol import ISlotRunPlanProtocol


def test_container_exposes_slot_config_protocol() -> None:
    """SharedContainer.slot_plan must satisfy ISlotRunPlanProtocol."""
    container = SharedContainer()
    assert isinstance(container.slot_plan, ISlotRunPlanProtocol)


def test_qwen_tui_app_receives_slot_config_via_constructor() -> None:
    """QwenTuiApp must get slot_config injected from the container, not imported."""
    container = SharedContainer()
    controller = InteractiveController(
        container.workspace,
        container.agent_direct_prompt_orchestrator,
        container.agent_prompt_file_orchestrator,
        container.agent_attachment_prompt_orchestrator,
        container.slot_plan,
        container.agent_setup_orchestrator,
        container.agent_session_orchestrator,
        container.agent_job_orchestrator,
        container.agent_swarm_orchestrator,
        container.session_manager,
    )

    with (
        patch("sys.stdin") as mock_stdin,
        patch("modules.cli.src.surface_cli_tui_app.QwenTuiApp") as mock_app,
    ):
        mock_stdin.isatty.return_value = True
        result = controller.run()

    assert result["success"] is True
    mock_app.assert_called_once()
    # 5th positional constructor argument is slot_config (ISlotRunPlanProtocol).
    injected = mock_app.call_args.args[4]
    assert injected is container.slot_plan
    assert isinstance(injected, ISlotRunPlanProtocol)


def test_controller_forwards_slot_config_without_capability_import() -> None:
    """InteractiveController must forward the injected resolver unchanged."""
    slot_config = MagicMock(spec=ISlotRunPlanProtocol)
    controller = InteractiveController(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        slot_config,
    )
    assert controller._slot_config is slot_config


def test_surface_does_not_import_slot_config_capability() -> None:
    """AR-1: TUI surface modules must not import the capability by concrete name."""
    src_dir = Path(__file__).resolve().parents[1] / "src"
    offenders = [
        path.name
        for path in src_dir.glob("surface_cli_*.py")
        if "capabilities_slot_plan_resolver" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
