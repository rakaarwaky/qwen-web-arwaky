"""Unit tests for ConfigOrchestrator: config building and timeout reporting."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.core.src.agent_config_orchestrator import ConfigOrchestrator
from modules.shared.src.taxonomy_core_vo import Mode, TimeoutSec


def test_for_mode_passes_mode_and_paths_through() -> None:
    with patch("modules.core.src.agent_config_orchestrator.build_app_config") as build:
        ConfigOrchestrator().for_mode(
            Mode("prompt-direct"),
            input_path=Path("/tmp/in.md"),
            output_path=Path("/tmp/out.md"),
            headless=False,
        )

    kwargs = build.call_args.kwargs
    assert build.call_args.args[0] == "prompt-direct"
    assert kwargs["input_path"] == Path("/tmp/in.md")
    assert kwargs["output_path"] == Path("/tmp/out.md")
    assert kwargs["headless"] is False


def test_for_mode_uses_defaults_for_unspecified_fields() -> None:
    with patch("modules.core.src.agent_config_orchestrator.build_app_config") as build:
        ConfigOrchestrator().for_mode(Mode("job"))

    kwargs = build.call_args.kwargs
    assert build.call_args.args[0] == "job"
    assert kwargs["input_path"] is None
    assert kwargs["headless"] is True


def test_request_timeout_sec_reflects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "1234")

    assert ConfigOrchestrator().request_timeout_sec() == TimeoutSec(1234)


def test_request_timeout_sec_ignores_unparseable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "not-a-number")

    assert ConfigOrchestrator().request_timeout_sec() == TimeoutSec(600)


def test_request_timeout_sec_ignores_non_positive_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "0")

    assert ConfigOrchestrator().request_timeout_sec() == TimeoutSec(600)


def test_request_timeout_sec_uses_default_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_REQUEST_TIMEOUT_SEC", raising=False)

    assert ConfigOrchestrator().request_timeout_sec() == TimeoutSec(600)


def test_for_mode_sandbox_flag_follows_host_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)

    with patch(
        "modules.core.src.utility_core_config_factory.sandbox_unavailable",
        return_value=True,
    ):
        cfg = ConfigOrchestrator().for_mode(Mode("prompt-direct"))

    assert cfg.disable_sandbox is True


def test_for_mode_env_can_force_sandbox_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_ENABLE_SANDBOX", "1")
    monkeypatch.setenv("QWEN_DISABLE_SANDBOX", "")

    with patch(
        "modules.core.src.utility_core_config_factory.sandbox_unavailable",
        return_value=True,
    ):
        cfg = ConfigOrchestrator().for_mode(Mode("prompt-direct"))

    assert cfg.disable_sandbox is False


def test_request_timeout_sec_reads_env_each_call(monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrator = ConfigOrchestrator()

    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "10")
    first = orchestrator.request_timeout_sec()
    monkeypatch.setenv("QWEN_REQUEST_TIMEOUT_SEC", "20")
    second = orchestrator.request_timeout_sec()

    assert first == TimeoutSec(10)
    assert second == TimeoutSec(20)
    assert os.environ["QWEN_REQUEST_TIMEOUT_SEC"] == "20"
