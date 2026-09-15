"""CLI surface: update command — self-update & environment synchronization (AES406).

Smart surface: presentation only. Version discovery, pip upgrade, Playwright
Chromium synchronization, and post-flight health checks are owned by the update
manager capability (IUpdateProtocol); this surface formats reports and maps
outcomes to the standardized success/error response envelope.
"""

from __future__ import annotations

from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
)
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response

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
    lines.append("")
    return "\n".join(lines)


@safe_handle
def handle(args: object, updater: IUpdateProtocol) -> dict[str, object]:
    """Dispatch the update subcommand to the update manager capability."""
    check_only = bool(getattr(args, "check", False))
    force = bool(getattr(args, "force", False))

    if check_only:
        result = updater.check_update()
        if result.latest_version is None:
            return error_response(
                RuntimeError(f"Update check failed: {result.error or 'version source unavailable'}"),
                "update_check_failed",
                "cli-502",
            )
        return success_response(_format_check_result(result))

    report = updater.perform_update(ForceFlag(force))
    if not report.healthy:
        return error_response(
            RuntimeError(_format_report(report)),
            "update_failed",
            "cli-422",
        )
    return success_response(_format_report(report))
