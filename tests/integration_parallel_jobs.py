"""Integration tests for parallel job submission and ephemeral browser sessions."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_job_manager import JobManager
from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.taxonomy_core_vo import (
    HeadlessFlag,
    ResponseText,
)


def test_shared_container_wires_max_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_WEB_MAX_WORKERS", raising=False)
    container = SharedContainer(max_workers=3)
    orch = cast(AgentJobOrchestrator, container.agent_job_orchestrator)
    assert orch._executor._max_workers == 3


def test_shared_container_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_WEB_MAX_WORKERS", "5")
    container = SharedContainer()
    orch = cast(AgentJobOrchestrator, container.agent_job_orchestrator)
    assert orch._executor._max_workers == 5


def test_agent_job_orchestrator_runs_n_jobs_in_parallel() -> None:
    """Confirm N jobs start nearly simultaneously (max_workers=3, sleep gate)."""
    with tempfile.TemporaryDirectory() as tmp:
        storage = JobManager(storage_dir=Path(tmp))
        file_only = MagicMock()
        attachment = MagicMock()

        def fake_process(**_kw: Any) -> ResponseText:
            time.sleep(0.5)
            return ResponseText("ok")

        file_only.process_prompt_file_only.side_effect = fake_process

        orch = AgentJobOrchestrator(
            storage=storage,
            file_only=file_only,
            attachment=attachment,
            max_workers=3,
        )

        for i in range(3):
            prompt = Path(tmp) / f"p_{i}.md"
            prompt.write_text("hi", encoding="utf-8")
            orch.submit_file_job(prompt_file=prompt, headless=HeadlessFlag(True))

        # Three parallel jobs at 0.5s each should finish in well under 1.5s serial.
        deadline = time.monotonic() + 3.0
        done = 0
        while time.monotonic() < deadline:
            done = sum(1 for j in orch.list_jobs(limit=10) if j.completed)
            if done == 3:
                break
            time.sleep(0.05)
        orch._executor.shutdown(wait=True)
        assert done == 3
        assert any((j.duration_sec or 0) >= 0.4 for j in orch.list_jobs(limit=10))


def test_browser_adapter_uses_ephemeral_session_for_jobs(tmp_path: Path) -> None:
    adapter = BrowserAdapter()
    master_session = tmp_path / "master_session"
    master_session.mkdir()
    (master_session / "Cookies").write_text("cookie_auth", encoding="utf-8")

    cfg = MagicMock()
    cfg.session_path = master_session
    cfg.mode = "prompt-only"
    cfg.headless = True
    cfg.disable_sandbox = False

    observed_user_data_dir: list[Any] = []

    def fake_launch(_p: Any, kwargs: dict[str, Any]) -> Any:
        observed_user_data_dir.append(kwargs.get("user_data_dir"))
        ctx = MagicMock()
        ctx.pages = []
        return ctx

    with patch.object(adapter, "_launch_context", side_effect=fake_launch):
        with adapter.browser_session(cfg):
            pass

    assert len(observed_user_data_dir) == 1
    used_dir = Path(observed_user_data_dir[0])
    # Must NOT be master session
    assert used_dir != master_session
    # Ephemeral dir must have been cleaned up after session exit
    assert not used_dir.exists()


def test_browser_adapter_login_mode_uses_master_session(tmp_path: Path) -> None:
    adapter = BrowserAdapter()
    master_session = tmp_path / "master_session"

    cfg = MagicMock()
    cfg.session_path = master_session
    cfg.mode = "login"
    cfg.headless = False
    cfg.disable_sandbox = False

    observed_user_data_dir: list[Any] = []

    def fake_launch(_p: Any, kwargs: dict[str, Any]) -> Any:
        observed_user_data_dir.append(kwargs.get("user_data_dir"))
        ctx = MagicMock()
        ctx.pages = []
        return ctx

    with patch.object(adapter, "_launch_context", side_effect=fake_launch):
        with adapter.browser_session(cfg):
            pass

    assert len(observed_user_data_dir) == 1
    assert Path(observed_user_data_dir[0]) == master_session
