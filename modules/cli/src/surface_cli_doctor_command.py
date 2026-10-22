"""CLI surface: doctor command — system diagnostic checks (AES406).

Wraps the capabilities health probe (``capabilities_config_health_probe``)
for interactive presentation. All diagnostic checks live in the Capabilities
layer; the CLI Surface owns only ``run_doctor`` (formatted output) and
``summarize`` (report aggregation).

The library form is ``capabilities_config_health_probe.run_doctor_checks``;
every caller — the CLI report and the update pipeline's postflight gate —
injects a session aggregate, so doctor and ``session list`` can never
disagree about the pool (issue #294). The failure footer points at the
operator runbooks (issue #299).
"""

from __future__ import annotations

from typing import Any

from modules.cli.src.surface_cli_json_hook import status_glyph
from modules.config.src.capabilities_config_health_probe import (
    _check_capacity,  # noqa: F401 — re-exported for test backward compatibility
    _check_chromium,  # noqa: F401 — re-exported for test backward compatibility
    _check_sandbox,  # noqa: F401 — re-exported for test backward compatibility
    _flag,
    _sandbox_mode,  # noqa: F401 — re-exported for test backward compatibility
    _sandbox_unavailable,  # noqa: F401 — re-exported for test backward compatibility
    build_smoke_gate,
    run_doctor_checks,
)
from modules.shared.src.common.utility_core_capacity import (
    recommended_max_workers,
)
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.update.utility_update_chromium import (
    playwright_browsers_path,  # noqa: F401 — re-exported for test backward compatibility
)

RULE = "─" * 50


def _check(name: str, passed: bool, detail: str, severity: str = "ok") -> dict[str, Any]:
    """Build one diagnostic record.

    Severity vocabulary: ``"ok"`` for a passing check, ``"warning"`` for a
    check that passes with a concern worth surfacing, and ``"error"`` only
    for ``passed=False`` — so a report consumer can tell a hard failure from
    a soft concern.
    """
    return {"name": name, "passed": passed, "detail": detail, "severity": severity}


def summarize(checks: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """Split checks into the all-passed flag plus the failed and warning lists."""
    failed = [c for c in checks if not c["passed"]]
    warned = [c for c in checks if c["passed"] and c.get("severity") == "warning"]
    return not failed, failed, warned


def run_doctor(
    session: ISessionAggregate,
    json_output: bool = False,
    smoke: bool = False,
    deep: bool = False,
) -> int:
    """Perform system health diagnostics and print a formatted report or JSON summary.

    With ``smoke`` enabled, a final check runs a headless browser round-trip
    on the saved session to verify the full pipeline end-to-end (issue #322).
    ``--deep`` (or the ``QWEN_DOCTOR_DEEP`` alias) runs the heavy Playwright
    probe; *deep* and the flag are OR-ed, the env var is only an alias.
    """
    import json as _json

    include_heavy = deep or _flag("QWEN_DOCTOR_DEEP")
    checks = run_doctor_checks(session=session, include_heavy=include_heavy, smoke=smoke)
    all_passed, _failed, _warned = summarize(checks)
    if json_output:
        from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MAX_WORKERS
        from modules.shared.src.common.utility_core_env import effective_config, runbook_index

        print(
            _json.dumps(
                {
                    "status": "healthy" if all_passed else "unhealthy",
                    "checks": checks,
                    "environment": effective_config(),
                    "capacity": {
                        "recommended_max_workers": recommended_max_workers(),
                        "max_workers_cap": DEFAULT_MAX_WORKERS,
                    },
                    "runbooks": runbook_index(),
                },
                indent=2,
            )
        )
        return 0 if all_passed else 1

    print("\n🔍 Qwen Web Automation System Health Diagnostic\n" + RULE)
    failed_count = 0
    warned_count = 0
    for check in checks:
        if not check["passed"]:
            icon = status_glyph("fail")
            failed_count += 1
        elif check.get("severity") == "warning":
            icon = status_glyph("warn")
            warned_count += 1
        else:
            icon = status_glyph("ok")
        print(f"  {icon} {check['name']}")
        print(f"      {check['detail']}")

    print(RULE)
    if failed_count:
        print(f"{status_glyph('warn')} {failed_count} check(s) failed; fix items marked {status_glyph('fail')} above.")
        print(f"   Operator runbooks: {RUNBOOK_ROOT} (keyed by ErrorCategory)\n")
        return 1
    if warned_count:
        print(f"{status_glyph('warn')} All checks passed with {warned_count} warning(s); runbooks at {RUNBOOK_ROOT}")
        print(f"   Operator runbooks: {RUNBOOK_ROOT}\n")
        return 0
    print(f"{status_glyph('ok')} All diagnostic checks passed! System is healthy and ready for execution.\n")
    return 0


RUNBOOK_ROOT = "docs/"


__all__ = [
    "build_smoke_gate",
    "run_doctor",
    "run_doctor_checks",
    "summarize",
]
