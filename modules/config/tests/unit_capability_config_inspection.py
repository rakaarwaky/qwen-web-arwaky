"""Unit tests for the four config capability seams.

Each seam is a stateless read of the process environment or the host, so
every test drives it through ``monkeypatch`` and asserts on the returned
value object rather than on a log line.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.config.src.capabilities_config_capacity import ConfigCapacityAdvisor
from modules.config.src.capabilities_config_environment import ConfigEnvironment
from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.taxonomy_core_vo import AppConfig

# ─── ConfigEnvironment ────────────────────────────────────────────────────


def test_sandbox_is_on_by_default_on_a_capable_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)

    with patch(
        "modules.config.src.capabilities_config_environment._sandbox_host_unavailable",
        return_value=False,
    ):
        report = ConfigEnvironment().sandbox_report()

    assert report.state == "sandboxed"
    assert report.host_supports_sandbox is True


def test_disable_env_outranks_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("QWEN_ENABLE_SANDBOX", "1")

    report = ConfigEnvironment().sandbox_report()

    assert report.state == "disabled_by_env"
    assert "QWEN_DISABLE_SANDBOX" in report.reason


def test_enable_env_beats_host_limitation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.setenv("QWEN_ENABLE_SANDBOX", "1")

    with patch(
        "modules.config.src.capabilities_config_environment._sandbox_host_unavailable",
        return_value=True,
    ):
        report = ConfigEnvironment().sandbox_report()

    assert report.state == "forced"
    assert report.host_supports_sandbox is True


def test_host_limitation_disables_sandbox_when_no_env_says_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)

    with patch(
        "modules.config.src.capabilities_config_environment._sandbox_host_unavailable",
        return_value=True,
    ):
        report = ConfigEnvironment().sandbox_report()

    assert report.state == "disabled_by_host"
    assert report.host_supports_sandbox is False


def test_max_workers_prefers_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_WEB_MAX_WORKERS", "11")

    with patch(
        "modules.config.src.capabilities_config_environment.recommended_max_workers",
        return_value=3,
    ):
        assert ConfigEnvironment().max_workers() == 11


def test_max_workers_falls_back_to_memory_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_WEB_MAX_WORKERS", "not-a-number")

    with patch(
        "modules.config.src.capabilities_config_environment.recommended_max_workers",
        return_value=3,
    ):
        assert ConfigEnvironment().max_workers() == 3


def test_swarm_headless_is_off_only_for_an_explicit_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWA_SWARM_HEADLESS", raising=False)
    assert ConfigEnvironment().swarm_headless() is True

    monkeypatch.setenv("QWA_SWARM_HEADLESS", "0")
    assert ConfigEnvironment().swarm_headless() is False

    monkeypatch.setenv("QWA_SWARM_HEADLESS", "false")
    assert ConfigEnvironment().swarm_headless() is False


def test_model_reads_the_pinned_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_DEFAULT_MODEL", "Qwen3.8-Max-Plus")
    assert ConfigEnvironment().model() == "Qwen3.8-Max-Plus"

    monkeypatch.delenv("QWEN_DEFAULT_MODEL", raising=False)
    assert ConfigEnvironment().model() == ""


# ─── ConfigValidator ──────────────────────────────────────────────────────


def _config(**overrides: object) -> AppConfig:
    """Return an AppConfig with the given field overrides applied.

    Field values are resolved against *tmp_path* when the underlying
    ``pathlib.Path`` constructor is called, so the validator's path
    existence checks do not pollute the result. Only non-path fields
    that the validator flags — ``request_timeout``, ``rate_limit_per_minute``,
    and ``circuit_breaker_threshold`` — are overridden here.
    """
    base: dict[str, object] = {
        "input_path": Path("/tmp/qwa_in.md"),
        "output_path": Path("/tmp/qwa_out.md"),
        "session_path": Path("/tmp/qwa_session"),
    }
    base.update(overrides)
    return AppConfig(**base)  # type: ignore[arg-type]


def test_validator_reports_nothing_for_a_usable_config(tmp_path: Path) -> None:
    target = tmp_path / "in.md"
    target.write_text("# hello", encoding="utf-8")
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "o.md").touch()
    (tmp_path / "session").mkdir()

    issues = ConfigValidator().validate(
        _config(
            input_path=target,
            output_path=tmp_path / "out" / "o.md",
            session_path=tmp_path / "session",
        )
    )

    assert issues.ok
    assert issues.errors == ()


def test_validator_lists_every_bad_field_at_once() -> None:
    # Build an AppConfig with minimum values, then downgrade the fields the
    # validator checks so the validator — not the constructor — reports them.
    app_config = _config()
    bad_fields = [
        ("timeout", 5),
        ("poll_interval", 0.1),
        ("request_timeout", 5),
        ("rate_limit_per_minute", 0),
        ("circuit_breaker_threshold", 1),
    ]
    for field, value in bad_fields:
        object.__setattr__(app_config, field, value)

    issues = ConfigValidator().validate(app_config)

    fields = {issue.field for issue in issues.errors}
    assert "timeout" in fields
    assert "poll_interval" in fields
    assert "request_timeout" in fields
    assert "rate_limit_per_minute" in fields
    assert "circuit_breaker_threshold" in fields


def test_validator_reports_a_missing_input_path(tmp_path: Path) -> None:
    target = tmp_path / "missing.md"
    issues = ConfigValidator().validate(_config(input_path=target))

    assert any(issue.field == "input_path" for issue in issues.errors)


def test_validator_treats_a_non_writable_output_directory_as_a_warning(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    target = locked / "out.md"
    with patch("modules.config.src.capabilities_config_validator._is_writable", return_value=False):
        issues = ConfigValidator().validate(_config(input_path=tmp_path / "in.md", output_path=target))

    assert any(issue.field == "output_path" and issue.severity == "warning" for issue in issues.warnings)


# ─── ConfigPathResolver ───────────────────────────────────────────────────


def test_resolver_accepts_a_not_yet_created_output_directory(tmp_path: Path) -> None:
    (tmp_path / "session").mkdir()
    resolved = ConfigPathResolver().resolve_paths(
        _config(
            input_path=tmp_path / "session" / "in.md",
            output_path=tmp_path / "new" / "out.md",
            session_path=tmp_path / "session",
        )
    )

    assert resolved.ok
    assert any(p.role == "output_path" and p.writable for p in resolved.paths)


def test_resolver_reports_a_writable_output_directory(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    resolved = ConfigPathResolver().resolve_paths(_config(output_path=target))

    entry = next(p for p in resolved.paths if p.role == "output_path")
    assert entry.writable is True
    assert entry.exists is False


def test_resolver_flags_an_output_directory_that_rejects_writes(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        resolved = ConfigPathResolver().resolve_paths(_config(output_path=locked / "out.md"))
    finally:
        locked.chmod(0o700)

    assert not resolved.ok
    assert any(issue.field == "output_path" and issue.category == "file_io" for issue in resolved.issues)


def test_resolver_skips_fields_the_config_left_unset(tmp_path: Path) -> None:
    resolved = ConfigPathResolver().resolve_paths(_config(storage_state_file=None))

    assert not any(p.role == "storage_state_file" for p in resolved.paths)


# ─── ConfigCapacityAdvisor ────────────────────────────────────────────────


def test_capacity_uses_the_derived_limit_without_an_override() -> None:
    report = ConfigCapacityAdvisor(env={}).report()

    assert report.effective_max_workers == report.recommended_max_workers
    assert report.over_capacity is False


def test_capacity_reports_an_override_above_the_derived_limit() -> None:
    with patch("modules.config.src.capabilities_config_capacity.recommended_max_workers", return_value=2):
        report = ConfigCapacityAdvisor(env={"QWEN_WEB_MAX_WORKERS": "16"}).report()

    assert report.effective_max_workers == 16
    assert report.recommended_max_workers == 2
    assert report.over_capacity is True
    assert "QWEN_WEB_MAX_WORKERS" in report.source


def test_capacity_ignores_an_unparseable_override() -> None:
    with patch("modules.config.src.capabilities_config_capacity.recommended_max_workers", return_value=4):
        report = ConfigCapacityAdvisor(env={"QWEN_WEB_MAX_WORKERS": "many"}).report()

    assert report.effective_max_workers == 4
    assert report.over_capacity is False


def test_capacity_advisor_reads_the_process_environment_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_WEB_MAX_WORKERS", "7")
    with patch("modules.config.src.capabilities_config_capacity.recommended_max_workers", return_value=2):
        report = ConfigCapacityAdvisor().report()

    assert report.effective_max_workers == 7
    assert os.environ["QWEN_WEB_MAX_WORKERS"] == "7"
