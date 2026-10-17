"""CLI surface: update command — self-update & environment synchronization (AES406).

Smart surface: maps parsed args to the IUpdateAggregate verbs
(check_update, perform_update, rollback_to) and formats reports.
"""

from __future__ import annotations

import json
import sys

from modules.shared.src.common.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
)
from modules.shared.src.common.utility_response_normalizer import error_response, safe_handle, success_response
from modules.shared.src.update.contract_update_aggregate import IUpdateAggregate
from modules.shared.src.update.taxonomy_update_vo import UpdateRequest

_DIVIDER = "─" * 58

def _step_icon(step: UpdateStepResult) -> str:
    """Return the terminal status icon for one pipeline step."""
    if not step.executed:
        return "[–]"
    return "[✓]" if step.success else "[✗]"

def _step_detail(step: UpdateStepResult) -> str:
    """Return the human-readable detail line for one pipeline step."""
    if step.detail:
        return step.detail
    if step.skipped_reason:
        return f"skipped — {step.skipped_reason}"
    return "ok"

def _format_check_result(res: UpdateCheckResult) -> str:
    """Format a read-only --check probe into a terminal report."""
    lines = [
        "",
        "🔎 Qwen Web Automation Update Check",
        _DIVIDER,
        f"  Package          : {res.package_name}",
        f"  Current version  : {res.current_version}",
    ]
    if res.latest_version is None:
        lines.append(f"  Latest version   : unavailable (source: {res.source})")
        if res.error:
            lines.append(f"  Diagnostic       : {res.error}")
    else:
        lines.append(f"  Latest version   : {res.latest_version} (source: {res.source})")
        lines.append(f"  Update available : {'yes' if res.update_available else 'no'}")
    lines.append(_DIVIDER)
    if res.latest_version is None:
        lines.append("⚠️ Could not determine the latest published version. Check network access and retry.")
    elif res.update_available:
        lines.append(f"⬆️ Run `qwen-web-arwaky update` to upgrade to {res.latest_version}.")
    else:
        lines.append("✅ You are already running the latest version.")
    lines.append("")
    return "\n".join(lines)

def _format_report(report: UpdateReport) -> str:
    """Format a full update run (steps + health checks) into a terminal report."""
    lines = [
        "",
        "🔄 Qwen Web Automation Self-Update & Environment Synchronization",
        _DIVIDER,
        f"  Package          : {report.package_name}",
        f"  Previous version : {report.previous_version}",
        f"  Latest version   : {report.latest_version or 'unknown'} (source: {report.source})",
        f"  Forced reinstall : {'yes' if report.forced else 'no'}",
        f"  Rolled back      : {'yes' if report.rolled_back else 'no'} ({report.rollback_status})",
    ]
    if report.steps:
        lines.append("")
        lines.append("  Steps:")
        for step in report.steps:
            lines.append(f"    {_step_icon(step)} {step.name}: {_step_detail(step)}")
    if report.health_checks:
        lines.append("")
        lines.append("  Post-update health checks:")
        for check in report.health_checks:
            lines.append(f"    {_step_icon(check)} {check.name}: {_step_detail(check)}")
    lines.append(_DIVIDER)
    lines.append(f"{'✅' if report.healthy else '⚠️'} {report.message}")
    if report.healthy and report.changed:
        lines.append("")
        lines.append(
            "💡 Note: If you have active MCP server or TUI sessions running in background, "
            "please restart them to ensure the newly installed package and Playwright browser are active (Issue #295)."
        )
    lines.append("")
    return "\n".join(lines)

@safe_handle
def handle(
    args: object,
    orchestrator: IUpdateAggregate,
) -> dict[str, object]:
    """Dispatch the update subcommand to the update aggregate verbs."""
    check_only = bool(getattr(args, "check", False))
    force = bool(getattr(args, "force", False))

    if check_only:
        response = orchestrator.execute(UpdateRequest(verb="check_update"))
        if response.error or response.check_result is None:
            reason = response.error or "update check returned no result"
            return error_response(
                RuntimeError(f"Update check failed: {reason}"),
                "update_check_failed",
                "cli-502",
            )
        return success_response(_format_check_result(response.check_result))

    response = orchestrator.execute(
        UpdateRequest(verb="perform_update", force=ForceFlag(force))
    )
    if response.error or response.report is None:
        reason = response.error or "update returned no report"
        return error_response(
            RuntimeError(reason),
            "update_failed",
            "cli-422",
        )
    return success_response(_format_report(response.report))

def handle_rollback(args: object, orchestrator: IUpdateAggregate) -> int:
    """Handle the --rollback subcommand of update: restore a previous version."""
    version = str(getattr(args, "rollback", "")).strip()
    if not version:
        print("[ERROR] --rollback requires a version, e.g. 'qwen-web-arwaky update --rollback 6.3.0'", file=sys.stderr)
        return 1

    json_output = bool(getattr(args, "json", False))
    response = orchestrator.execute(UpdateRequest(verb="rollback_to", previous_version=version))

    if response.error:
        msg = f"Rollback failed: {response.error}"
        if json_output:
            print(json.dumps({"success": False, "error": response.error}, indent=2))
        else:
            print(f"❌ {msg}", file=sys.stderr)
        return 1

    if response.steps:
        lines = ["", "↩️  Rolling back to " + version, _DIVIDER]
        for step in response.steps:
            lines.append(f"  {_step_icon(step)} {step.name}: {_step_detail(step)}")
        lines.append(_DIVIDER)
        report = "\n".join(lines)
    else:
        report = f"✅ Rollback to {version} completed."

    print(report)
    return 0


__all__ = ["handle", "handle_rollback"]
