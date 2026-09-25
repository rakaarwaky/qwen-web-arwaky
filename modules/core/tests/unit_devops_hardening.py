"""Unit tests for the DevOps hardening: sandbox default, smoke gate, degradation.

Covers the three behaviours that make a production host safe by default:

* #290 — Chromium keeps its OS sandbox unless the caller, an explicit env
  switch, or a host that cannot support one asks otherwise.
* #294 — the update pipeline runs an injected functional gate after a
  successful upgrade and treats a failure as a reason to roll back.
* #297 — a production host with no error-tracking backend says so instead of
  degrading to "off" without a word.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src import utility_core_session_guard as session_guard
from modules.core.src.capabilities_observability_setup import effective_telemetry_mode
from modules.core.src.capabilities_update_manager import UpdateManager
from modules.core.src.utility_core_config_factory import build_app_config, sandbox_unavailable
from modules.shared.src.taxonomy_core_vo import AppConfig

# ─── #290: sandbox is on by default ─────────────────────────────────────────


def test_app_config_defaults_to_a_sandboxed_browser() -> None:
    """No opt-in and a sandbox-capable host means the sandbox stays on."""
    with (
        patch.dict("os.environ", {}, clear=False),
        patch("modules.core.src.utility_core_config_factory.sandbox_unavailable", return_value=False),
        patch("os.environ", {"QWEN_DISABLE_SANDBOX": "", "QWEN_ENABLE_SANDBOX": ""}),
    ):
        assert build_app_config().disable_sandbox is False


def test_sandbox_dropped_on_explicit_opt_in() -> None:
    """QWEN_DISABLE_SANDBOX is the documented way to drop the sandbox."""
    with (
        patch("modules.core.src.utility_core_config_factory.sandbox_unavailable", return_value=False),
        patch("os.environ", {"QWEN_DISABLE_SANDBOX": "1"}),
    ):
        assert build_app_config().disable_sandbox is True


def test_sandbox_dropped_when_the_host_cannot_provide_one() -> None:
    """A container with no seccomp filter and no user namespaces falls back."""
    with (
        patch("modules.core.src.utility_core_config_factory.sandbox_unavailable", return_value=True),
        patch("os.environ", {"QWEN_DISABLE_SANDBOX": "", "QWEN_ENABLE_SANDBOX": ""}),
    ):
        assert build_app_config().disable_sandbox is True


def test_qwen_enable_sandbox_forces_the_sandbox_on_in_a_container() -> None:
    """QWEN_ENABLE_SANDBOX overrides the container detection."""
    with (
        patch("modules.core.src.utility_core_config_factory.sandbox_unavailable", return_value=True),
        patch("os.environ", {"QWEN_ENABLE_SANDBOX": "1"}),
    ):
        assert build_app_config().disable_sandbox is False


def test_sandbox_unavailable_returns_a_bool_on_this_host() -> None:
    assert isinstance(sandbox_unavailable(), bool)


def test_sandbox_flag_reaches_playwright_only_when_dropped(tmp_path) -> None:
    """The launch kwargs carry ``--no-sandbox`` iff the config dropped the sandbox."""
    from modules.core.src import capabilities_browser_adapter as adapter_module

    captured: list[dict] = []

    class _Context:
        def __init__(self, **kwargs: object) -> None:
            captured.append(dict(kwargs))

        def __enter__(self) -> _Context:
            return self

        def __exit__(self, *_exc: object) -> Literal[False]:
            return False

        def new_page(self) -> object:
            return object()

    class _Chromium:
        executable_path = "/usr/bin/chromium"

        def launch_persistent_context(self, **kwargs: object) -> _Context:
            return _Context(**kwargs)

    class _Playwright:
        chromium = _Chromium()

        def __enter__(self) -> _Playwright:
            return self

        def __exit__(self, *_exc: object) -> Literal[False]:
            return False

    session = tmp_path / "session"
    session.mkdir()
    (session / "Cookies").write_text("x", encoding="utf-8")

    adapter = adapter_module.BrowserAdapter()
    with (
        patch.object(adapter_module, "create_ephemeral_session") as ephemeral,
        patch.object(adapter_module, "find_chrome_binary", return_value="/usr/bin/chromium"),
        patch.object(adapter_module, "sync_playwright", return_value=_Playwright()),
    ):
        ephemeral.return_value.__enter__ = lambda self=None: session
        ephemeral.return_value.__exit__ = lambda *_exc: False
        for disable in (False, True):
            cfg = AppConfig(
                input_path=session,
                output_path=session,
                session_path=session,
                disable_sandbox=disable,
                headless=True,
            )
            try:
                with adapter.browser_session(cfg):
                    pass
            except Exception:
                pass

    sandboxed = [c for c in captured if "--no-sandbox" not in c.get("args", [])]
    unsandboxed = [c for c in captured if "--no-sandbox" in c.get("args", [])]
    assert sandboxed, "a sandboxed launch must not pass --no-sandbox"
    assert unsandboxed, "a dropped sandbox must pass --no-sandbox"


# ─── #294: post-update functional smoke gate ───────────────────────────────


def test_smoke_gate_is_a_noop_when_none_is_injected() -> None:
    manager = UpdateManager()
    assert manager._run_smoke_gate() == ()


def test_smoke_gate_failures_become_failed_health_checks() -> None:
    gate = lambda: (("Host Capacity", False, "recommended max workers 0"),)  # noqa: E731
    results = UpdateManager(smoke_gate=gate)._run_smoke_gate()

    assert len(results) == 1
    assert results[0].name == "smoke:Host Capacity"
    assert results[0].executed is True
    assert results[0].success is False
    assert "recommended max workers 0" in results[0].detail


def test_smoke_gate_passes_when_every_check_passes() -> None:
    gate = lambda: (("Host Capacity", True, "10 recommended max workers"),)  # noqa: E731
    results = UpdateManager(smoke_gate=gate)._run_smoke_gate()

    assert results[0].success is True


def test_smoke_gate_exception_becomes_a_failed_check_not_a_crash() -> None:
    def explode() -> tuple[tuple[str, bool, str], ...]:
        raise RuntimeError("doctor crashed")

    results = UpdateManager(smoke_gate=explode)._run_smoke_gate()

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].executed is True
    assert "doctor crashed" in results[0].detail


# ─── #297: observability degradation is explicit ────────────────────────────


def test_telemetry_mode_reports_file_only_when_nothing_is_configured() -> None:
    with patch("os.environ", {"SENTRY_DSN": "", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
        assert effective_telemetry_mode() == "file_only"


def test_telemetry_mode_reports_sentry_when_only_sentry_is_configured() -> None:
    with patch("os.environ", {"SENTRY_DSN": "https://x@y/1", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
        assert effective_telemetry_mode() == "sentry"


def test_telemetry_mode_reports_otlp_when_only_otlp_is_configured() -> None:
    with patch("os.environ", {"SENTRY_DSN": "", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"}):
        assert effective_telemetry_mode() == "otlp"


def test_telemetry_mode_reports_full_when_both_are_configured() -> None:
    with patch("os.environ", {"SENTRY_DSN": "https://x@y/1", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://c:4318"}):
        assert effective_telemetry_mode() == "full"


def test_doctor_warns_when_production_has_no_error_tracking(capsys) -> None:
    """A production host without a backend gets a warning, not a silent 'off'."""
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    with patch("os.environ", {"ENVIRONMENT": "production", "SENTRY_DSN": "", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
        run_doctor(json_output=False)
    out = capsys.readouterr().out
    assert "Observability Backends" in out
    assert "file log" in out


def test_doctor_does_not_warn_in_development_without_a_backend(capsys) -> None:
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    with patch("os.environ", {"ENVIRONMENT": "development", "SENTRY_DSN": "", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}):
        run_doctor(json_output=False)
    out = capsys.readouterr().out
    observability_line = [line for line in out.splitlines() if "Observability Backends" in line]
    # The check name is present but the production-only warning text is not.
    assert observability_line
    assert "ENVIRONMENT=production" not in out


def test_degraded_observability_is_logged_at_setup(caplog) -> None:
    """setup_observability emits an explicit observability_degraded event for file-only mode."""
    from modules.core.src.capabilities_metrics_counter import MetricsCounter
    from modules.core.src.capabilities_observability_setup import ObservabilitySetup
    from modules.core.src.capabilities_status_writer import StatusFileWriter

    log_dir = Path("test.jsonl").parent
    with (
        patch("os.environ", {"SENTRY_DSN": "", "OTEL_EXPORTER_OTLP_ENDPOINT": ""}),
        caplog.at_level(logging.INFO, logger="capabilities_observability"),
    ):
        # The status writer and metrics counter are injected (issue #359); this
        # test only exercises the telemetry-mode branch, so the real ones are fine.
        obs = ObservabilitySetup(
            log_dir,
            StatusFileWriter(log_dir / "status.json"),
            MetricsCounter(metrics_path=log_dir / "metrics.json"),
        )
        obs.setup_observability(log_path=Path("test.jsonl"), attach_stderr=False)

    messages = [record.getMessage() for record in caplog.records]
    assert any("observability_degraded" in msg for msg in messages)


# ─── #292 / #300: doctor reports the environment contract and backup state ──


def test_doctor_warns_about_unrecognized_qwen_variables(capsys) -> None:
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    with patch("os.environ", {"QWEN_WEB_MAX_WORKS": "5"}):
        run_doctor(json_output=False)
    out = capsys.readouterr().out
    assert "Unrecognized Environment Variables" in out
    assert "QWEN_WEB_MAX_WORKS" in out


def test_doctor_reports_sandbox_mode(capsys) -> None:
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    run_doctor(json_output=False)
    out = capsys.readouterr().out
    assert "Chromium Sandbox" in out
    assert "sandbox" in out.lower()


def test_doctor_reports_host_capacity(capsys) -> None:
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    run_doctor(json_output=False)
    out = capsys.readouterr().out
    assert "Host Capacity" in out
    assert "recommended max workers" in out


def test_doctor_json_includes_environment_capacity_and_runbooks(capsys) -> None:
    """doctor --json echoes the masked env contract (#292) and runbook index (#299)."""
    import json

    from modules.cli.src.surface_cli_doctor_command import run_doctor

    with patch("os.environ", {"SENTRY_DSN": "https://public:secret@o1.ingest.sentry.io/9"}):
        run_doctor(json_output=True)
    data = json.loads(capsys.readouterr().out)

    assert data["environment"]["SENTRY_DSN"] == "***"
    assert "recommended_max_workers" in data["capacity"]
    assert "auth" in data["runbooks"]
    assert data["runbooks"]["auth"].startswith("docs/runbooks/")


def test_smoke_gate_builder_returns_name_passed_detail_triples() -> None:
    """build_smoke_gate is the callable the Root layer injects (#294)."""
    from modules.cli.src.surface_cli_doctor_command import build_smoke_gate

    gate = build_smoke_gate()
    results = gate()
    assert results
    for name, passed, detail in results:
        assert isinstance(name, str)
        assert isinstance(passed, bool)
        assert isinstance(detail, str)
    # The gate includes the non-interactive doctor checks.
    names = {name for name, _, _ in results}
    assert "Host Capacity" in names
    assert "Chromium Sandbox" in names
    assert "Browser Smoke Test" not in names


def test_root_container_wires_the_doctor_gate_into_the_updater() -> None:
    """Root composes the gate; the Capabilities updater only sees a callable."""
    from modules.core.src.root_core_container import SharedContainer

    container = SharedContainer()
    assert callable(getattr(container.updater, "_smoke_gate", None))
    results = container.updater._run_smoke_gate()
    assert any(r.name.startswith("smoke:") for r in results)


def test_delete_session_refuses_without_a_backup(tmp_path, monkeypatch) -> None:
    """delete_session refuses when no backup exists unless forced (#300)."""
    from modules.core.src import agent_session_orchestrator as session_module

    orch = session_module.SessionOrchestrator(browser=MagicMock(), observability=MagicMock())
    session = tmp_path / "qwen_session"
    session.mkdir()
    (session / "Cookies").write_text("x", encoding="utf-8")
    monkeypatch.setattr(session_guard, "DEFAULT_SESSION", session)

    with pytest.raises(Exception, match="no session backup is retained"):
        orch.delete_session(session)


def test_delete_session_proceeds_when_forced(tmp_path, monkeypatch) -> None:
    """force=True skips the backup guard so an operator can still delete."""
    from modules.core.src import agent_session_orchestrator as session_module

    orch = session_module.SessionOrchestrator(browser=MagicMock(), observability=MagicMock())
    session = tmp_path / "qwen_session"
    session.mkdir()
    (session / "Cookies").write_text("x", encoding="utf-8")
    monkeypatch.setattr(session_guard, "DEFAULT_SESSION", session)

    result = orch.delete_session(session, force=True)

    assert "deleted successfully" in str(result)
    assert not session.exists()
