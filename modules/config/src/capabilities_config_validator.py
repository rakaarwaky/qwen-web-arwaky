"""Capabilities: config validation (AES403).

Implements ``IConfigValidatorProtocol``.

Turns the minimum-field checks ``AppConfig`` already enforces into displayable
issues, and adds the path-existence checks ``AppConfig`` deliberately leaves to
the caller so a diagnostic can report them. ``AppConfig.validate`` raises on the
first bad field; this seam returns every problem so a run command can list them
and a doctor can show all of them at once.
"""

from __future__ import annotations

import time
from pathlib import Path

from modules.shared.src.contract_config_protocol import IConfigValidatorProtocol
from modules.shared.src.taxonomy_config_vo import ConfigCategory, ConfigIssue, ConfigIssues
from modules.shared.src.taxonomy_core_vo import AppConfig


class ConfigValidator(IConfigValidatorProtocol):
    """Report every problem that keeps an ``AppConfig`` from running."""

    def validate(self, app_config: AppConfig) -> ConfigIssues:
        """Return the issues in *app_config*; empty when it can run.

        Field minimums are checked against the same thresholds ``AppConfig``
        itself enforces, so a config that built successfully passes here
        unchanged and only the optional path targets contribute findings.
        """
        issues: list[ConfigIssue] = []

        minimums: tuple[tuple[str, float, float, ConfigCategory, str], ...] = (
            ("timeout", float(app_config.timeout), 30.0, "other", f"timeout is {app_config.timeout}s, minimum is 30s"),
            (
                "poll_interval",
                float(app_config.poll_interval),
                0.5,
                "response_timeout",
                f"poll_interval is {app_config.poll_interval}s, minimum is 0.5s",
            ),
            (
                "request_timeout",
                float(app_config.request_timeout),
                10.0,
                "response_timeout",
                f"request_timeout is {app_config.request_timeout}s, minimum is 10s",
            ),
            (
                "rate_limit_per_minute",
                float(app_config.rate_limit_per_minute),
                1.0,
                "other",
                f"rate_limit_per_minute is {app_config.rate_limit_per_minute}, minimum is 1",
            ),
            (
                "circuit_breaker_threshold",
                float(app_config.circuit_breaker_threshold),
                2.0,
                "other",
                f"circuit_breaker_threshold is {app_config.circuit_breaker_threshold}, minimum is 2",
            ),
        )
        for field_name, actual, floor, category, message in minimums:
            if actual < floor:
                issues.append(ConfigIssue(field=field_name, message=message, severity="error", category=category))

        for field_name in ("input_path", "output_path", "session_path"):
            value = getattr(app_config, field_name)
            if value is None:
                issues.append(
                    ConfigIssue(
                        field=field_name,
                        message=f"{field_name} is unset and a run needs one",
                        severity="error",
                        category="file_io",
                    )
                )
            else:
                issues.extend(self._path_issues(field_name, Path(value)))

        return ConfigIssues(issues=tuple(issues))

    @staticmethod
    def _path_issues(field: str, path: Path) -> list[ConfigIssue]:
        """Return the findings one config path contributes, empty when it is usable.

        Only ``input_path`` has to exist: it names a prompt the run reads.
        ``output_path`` names a file the run creates, so a missing one is
        expected and only its destination directory has to be usable.
        ``session_path`` names a profile a fresh install has not written
        yet, so it is checked the same way as the output.
        """
        findings: list[ConfigIssue] = []
        if field == "input_path" and not path.exists():
            findings.append(
                ConfigIssue(
                    field=field,
                    message=f"{field} {path} does not exist",
                    severity="error",
                    category="file_io",
                )
            )
            return findings
        parent = path if field == "session_path" and path.is_dir() else path.parent
        if not parent.exists():
            findings.append(
                ConfigIssue(
                    field=field,
                    message=f"{field} parent directory {parent} is missing and cannot be created",
                    severity="error",
                    category="file_io",
                )
            )
        elif not _is_writable(parent):
            findings.append(
                ConfigIssue(
                    field=field,
                    message=f"{field} directory {parent} is not writable",
                    severity="warning",
                    category="file_io",
                )
            )
        return findings


def _is_writable(directory: Path) -> bool:
    """Return True when the process can write a file into *directory*."""
    nonce = str(time.time_ns() % 100000000)
    probe = directory / f".qwa_probe_{nonce}"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


__all__ = ["ConfigValidator"]
