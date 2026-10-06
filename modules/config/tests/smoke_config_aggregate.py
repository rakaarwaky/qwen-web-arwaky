"""Smoke tests for the config aggregate.

The aggregate's promise is that a caller obtains a usable configuration from
one door, with every default filled in. These drive that door against the
real capability seams, so no stub stands between the request and the config
the pipeline would run with.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from modules.config.src.agent_config_orchestrator import ConfigOrchestrator
from modules.config.src.capabilities_config_capacity import ConfigCapacityAdvisor
from modules.config.src.capabilities_config_environment import ConfigEnvironment
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.taxonomy_config_vo import ConfigRequest
from modules.shared.src.taxonomy_core_vo import AppConfig, Mode


def _orchestrator() -> ConfigOrchestrator:
    return ConfigOrchestrator(
        environment=ConfigEnvironment(),
        validator=ConfigValidator(),
        path_resolver=ConfigPathResolver(),
        capacity=ConfigCapacityAdvisor(),
        slot_plan=SlotRunPlanResolver(),
    )


def test_smoke_the_aggregate_builds_a_config_for_one_mode(tmp_path: Path) -> None:
    response = _orchestrator().execute(
        ConfigRequest(
            verb="for_mode",
            mode=Mode("prompt-direct"),
            input_path=tmp_path / "in.md",
            output_path=tmp_path / "out.md",
        )
    )

    config = cast(AppConfig, response.config)
    assert config.mode == "prompt-direct"
    assert config.output_path == tmp_path / "out.md"


def test_smoke_the_aggregate_fills_unspecified_fields_from_defaults(tmp_path: Path) -> None:
    response = _orchestrator().execute(
        ConfigRequest(
            verb="for_mode",
            mode=Mode("job"),
            input_path=tmp_path / "in.md",
            output_path=tmp_path / "out.md",
        )
    )

    config = cast(AppConfig, response.config)
    assert config.headless is True
    assert config.log_path is not None
