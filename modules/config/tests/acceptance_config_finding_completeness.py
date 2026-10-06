"""Acceptance tests for the config finding-completeness requirement.

The requirement in `modules/config/FRD.md` FR-CONFIG-002 is that every
problem a config has is reported in one call, not just the first. These
seed a config with several invalid fields and assert all of them surface.
"""

from __future__ import annotations

from pathlib import Path

from modules.config.src.capabilities_config_validator import ConfigValidator
from modules.shared.src.taxonomy_core_vo import AppConfig


def _valid_config(tmp_path: Path) -> AppConfig:
    """Return a config whose every named path exists and is writable."""
    (tmp_path / "input.md").write_text("prompt", encoding="utf-8")
    (tmp_path / "session").mkdir()
    return AppConfig(
        mode="single",
        input_path=tmp_path / "input.md",
        output_path=tmp_path / "out.md",
        session_path=tmp_path / "session",
    )


def _config_with_violations(config: AppConfig) -> AppConfig:
    """Return *config* carrying three invalid field values.

    ``AppConfig`` validates on construction, so the fields are patched after
    the fact to reach the validator with the state a caller would otherwise
    have been unable to construct.
    """
    object.__setattr__(config, "timeout", 1)
    object.__setattr__(config, "poll_interval", 0.1)
    object.__setattr__(config, "request_timeout", 1)
    return config


def test_acceptance_every_violation_is_reported_in_one_call(tmp_path: Path) -> None:
    issues = ConfigValidator().validate(_config_with_violations(_valid_config(tmp_path)))

    fields = {issue.field for issue in issues.issues}
    assert {"timeout", "poll_interval", "request_timeout"} <= fields, (
        f"the validator reported {fields} but must report every violation, not the first"
    )


def test_acceptance_a_valid_config_reports_no_findings(tmp_path: Path) -> None:
    issues = ConfigValidator().validate(_valid_config(tmp_path))

    assert issues.issues == ()
    assert issues.ok is True
