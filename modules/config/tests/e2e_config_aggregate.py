"""End-to-end tests for the config aggregate over its verb surface.

These drive ``ConfigOrchestrator`` with the five real capability seams and
no network or browser, so the request-to-response path the other
orchestrators consume is exercised end to end: each verb resolves through
the real seams and returns a structured response. The environment-driven
policy is controlled through ``monkeypatch`` rather than global patches.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.config.src.agent_config_orchestrator import ConfigOrchestrator
from modules.config.src.capabilities_config_capacity import ConfigCapacityAdvisor
from modules.config.src.capabilities_config_environment import ConfigEnvironment
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.taxonomy_config_vo import ConfigRequest, ConfigResponse
from modules.shared.src.taxonomy_core_vo import AppConfig, Mode, OutputPath, PromptText, TimeoutSec


def _orchestrator() -> ConfigOrchestrator:
    """Return an orchestrator wired to the five real capability seams."""
    return ConfigOrchestrator(
        environment=ConfigEnvironment(),
        validator=ConfigValidator(),
        path_resolver=ConfigPathResolver(),
        capacity=ConfigCapacityAdvisor(),
        slot_plan=SlotRunPlanResolver(),
    )


def test_e2e_for_mode_builds_a_config_that_carries_its_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One request produces the built config and the ceiling it honors."""
    monkeypatch.delenv("QWEN_REQUEST_TIMEOUT_SEC", raising=False)
    request = ConfigRequest(
        verb="for_mode",
        mode=Mode("prompt-direct"),
        input_path=tmp_path / "in.md",
        output_path=tmp_path / "out.md",
    )
    response = _orchestrator().execute(request)

    assert isinstance(response, ConfigResponse)
    assert response.error is None, "the verb must answer without a structured error"
    config = response.config
    assert isinstance(config, AppConfig)
    assert config.mode == "prompt-direct"
    assert config.output_path == tmp_path / "out.md"
    assert response.timeout_sec is not None and TimeoutSec(response.timeout_sec) > 0


def test_e2e_environment_override_flows_into_the_built_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An operator-set ceiling wins over the default through the seam."""
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "120")
    request = ConfigRequest(
        verb="for_mode",
        mode=Mode("prompt-direct"),
        input_path=tmp_path / "in.md",
        output_path=tmp_path / "out.md",
    )
    response = _orchestrator().execute(request)

    assert response.config is not None
    assert TimeoutSec(response.config.request_timeout) == 120
    assert TimeoutSec(response.timeout_sec) == 120


def test_e2e_slot_plan_verb_resolves_a_run_plan_through_the_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The slot-plan verb resolves slot inputs through the real seam."""
    monkeypatch.delenv("QWEN_ROLE_TEMPLATE_DIR", raising=False)
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("# prompt\n", encoding="utf-8")
    request = ConfigRequest(
        verb="slot_plan",
        prompt_val=PromptText(str(prompt_file)),
        file_val=PromptText(""),
        output_val=OutputPath(tmp_path / "out.md"),
    )
    response = _orchestrator().execute(request)

    assert isinstance(response, ConfigResponse)
    # A named prompt file with a named output must resolve, not error.
    assert response.error is None, f"the slot plan must resolve: {response.error}"


def test_e2e_unknown_verb_is_rejected_with_a_structured_error() -> None:
    """The aggregate fails closed on a verb it does not own."""
    response = _orchestrator().execute(ConfigRequest(verb="not_a_verb"))

    assert isinstance(response, ConfigResponse)
    assert response.config is None
    assert response.error is not None and "not_a_verb" in response.error
