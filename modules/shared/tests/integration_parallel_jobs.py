"""Integration tests for parallel job submission and ephemeral browser sessions."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.root_core_container import SharedContainer
from modules.shared.src.jobs.taxonomy_jobs_vo import JobRequest
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptResponse


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
        storage = JobStorage(storage_dir=Path(tmp))
        file_only = MagicMock()
        attachment = MagicMock()

        def fake_execute(*_a: Any, **_kw: Any) -> PromptResponse:
            time.sleep(0.5)
            return PromptResponse(response_text="ok")

        file_only.execute.side_effect = fake_execute

        orch = AgentJobOrchestrator(
            storage=storage,
            file_only=file_only,
            attachment=attachment,
            max_workers=3,
        )

        for i in range(3):
            prompt = Path(tmp) / f"p_{i}.md"
            prompt.write_text("hi", encoding="utf-8")
            orch.execute(JobRequest(verb="submit_file_job", prompt_file=prompt, headless=True))

        # Three parallel jobs at 0.5s each should finish in well under 1.5s serial.
        deadline = time.monotonic() + 3.0
        done = 0
        while time.monotonic() < deadline:
            done = sum(1 for j in (orch.execute(JobRequest(verb="list_jobs", limit=10)).records or []) if j.completed)
            if done == 3:
                break
            time.sleep(0.05)
        orch._executor.shutdown(wait=True)
        assert done == 3
        assert any(
            (j.duration_sec or 0) >= 0.4 for j in (orch.execute(JobRequest(verb="list_jobs", limit=10)).records or [])
        )


def test_browser_adapter_uses_ephemeral_session_for_jobs(tmp_path: Path) -> None:
    """Job mode passes the prepared session path straight through to the browser.

    ProfilePreparer (session module) owns the ephemeral-clone decision; the
    browser capability receives a plain prepared Path and never clones itself.
    """
    from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics

    lifecycle = BrowserLifecycle(navigation=None, diagnostics=BrowserDiagnostics())
    master_session = tmp_path / "master_session"
    master_session.mkdir()
    (master_session / "Cookies").write_text("cookie_auth", encoding="utf-8")

    from modules.session.src.capabilities_session_profile_preparer import ProfilePreparer

    preparer = ProfilePreparer()

    cfg = MagicMock()
    cfg.session_path = master_session
    cfg.mode = "single"
    cfg.headless = True
    cfg.disable_sandbox = False

    observed_user_data_dir: list[Any] = []

    def fake_launch(_p: Any, kwargs: dict[str, Any]) -> Any:
        observed_user_data_dir.append(kwargs.get("user_data_dir"))
        ctx = MagicMock()
        ctx.pages = []
        return ctx

    with patch.object(lifecycle, "_launch_context", side_effect=fake_launch):
        with preparer.prepare(cfg) as prepared_path:
            with lifecycle.browser_session(cfg, session_path=prepared_path):
                pass

    assert len(observed_user_data_dir) == 1
    used_dir = Path(observed_user_data_dir[0])
    # Prepared path is the ephemeral clone, NOT the master session
    assert used_dir != master_session
    # Ephemeral dir cleaned up after session exit
    assert not used_dir.exists()


def test_browser_adapter_login_mode_uses_master_session(tmp_path: Path) -> None:
    from modules.browser.src.capabilities_browser_diagnostics import BrowserDiagnostics

    lifecycle = BrowserLifecycle(navigation=None, diagnostics=BrowserDiagnostics())
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

    with patch.object(lifecycle, "_launch_context", side_effect=fake_launch):
        with lifecycle.browser_session(cfg):
            pass

    assert len(observed_user_data_dir) == 1
    assert Path(observed_user_data_dir[0]) == master_session
