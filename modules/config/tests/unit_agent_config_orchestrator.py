"""Unit tests for ConfigOrchestrator: config building and timeout reporting.

The orchestrator requires all four capability seams, so every test here
builds a real set rather than a partial stub: the seams are stateless
probes over the process environment, and each test already controls that
environment through ``monkeypatch``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.config.src.agent_config_orchestrator import ConfigOrchestrator
from modules.config.src.capabilities_config_capacity import ConfigCapacityAdvisor
from modules.config.src.capabilities_config_environment import ConfigEnvironment
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.taxonomy_core_vo import ConfigRequest, Mode, TimeoutSec


def _orchestrator() -> ConfigOrchestrator:
    """Return an orchestrator wired to the four real capability seams.

    Each seam is a stateless read of the process environment, so a test
    that sets an env var with ``monkeypatch`` is exercising the real
    resolution path rather than a stub's echo.
    """
    return ConfigOrchestrator(
        environment=ConfigEnvironment(),
        validator=ConfigValidator(),
        path_resolver=ConfigPathResolver(),
        capacity=ConfigCapacityAdvisor(),
    )


def test_for_mode_passes_mode_and_paths_through(tmp_path: Path) -> None:
    cfg = _orchestrator().for_mode(
        ConfigRequest(
            verb="for_mode",
            mode=Mode("prompt-direct"),
            input_path=tmp_path / "in.md",
            output_path=tmp_path / "out.md",
            headless=False,
        )
    )

    assert cfg.mode == "prompt-direct"
    assert cfg.input_path == tmp_path / "in.md"
    assert cfg.output_path == tmp_path / "out.md"
    assert cfg.headless is False


def test_for_mode_uses_defaults_for_unspecified_fields() -> None:
    cfg = _orchestrator().for_mode(ConfigRequest(verb="for_mode", mode=Mode("job")))

    assert cfg.mode == "job"
    assert cfg.headless is True


def test_request_timeout_sec_reflects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "1234")

    assert _orchestrator().request_timeout_sec() == TimeoutSec(1234)


def test_request_timeout_sec_ignores_unparseable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "not-a-number")

    assert _orchestrator().request_timeout_sec() == TimeoutSec(600)


def test_request_timeout_sec_ignores_non_positive_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "0")

    assert _orchestrator().request_timeout_sec() == TimeoutSec(600)


def test_request_timeout_sec_uses_default_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_REQUEST_TIMEOUT_SEC", raising=False)

    assert _orchestrator().request_timeout_sec() == TimeoutSec(600)


def test_for_mode_sandbox_flag_follows_host_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)

    with patch(
        "modules.config.src.capabilities_config_environment._sandbox_host_unavailable",
        return_value=True,
    ):
        cfg = _orchestrator().for_mode(ConfigRequest(verb="for_mode", mode=Mode("prompt-direct")))

    assert cfg.disable_sandbox is True


def test_for_mode_env_can_force_sandbox_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_ENABLE_SANDBOX", "1")
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)

    cfg = _orchestrator().for_mode(ConfigRequest(verb="for_mode", mode=Mode("prompt-direct")))

    assert cfg.disable_sandbox is False


def test_request_timeout_sec_reads_env_each_call(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = _orchestrator()

    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "10")
    first = orchestrator.request_timeout_sec()
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "20")
    second = orchestrator.request_timeout_sec()

    assert first == TimeoutSec(10)
    assert second == TimeoutSec(20)
    assert os.environ["QWEN_REQUEST_TIMEOUT_SEC"] == "20"
