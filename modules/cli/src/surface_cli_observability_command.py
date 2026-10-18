"""CLI surface: observability command — query run metrics and quality reports.

Smart surface: maps parsed args to the IObservabilityAggregate verbs
(write_quality_report, metrics_snapshot) and formats the response as a
human-readable summary or JSON envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from modules.cli.src.surface_cli_json_hook import _fail_json
from modules.shared.src.logging.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.logging.taxonomy_logging_vo import (
    MetricsSnapshot,
    ObservabilityRequest,
)


def _cmd_report(args: argparse.Namespace, orchestrator: IObservabilityAggregate) -> int:
    """Write and display the quality report for the last run."""
    json_output = bool(getattr(args, "json", False))
    response = orchestrator.execute(ObservabilityRequest(verb="write_quality_report"))
    if not response.success:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1

    report_path = response.report_path
    if json_output:
        payload: dict[str, Any] = {"success": True, "report_path": str(report_path)}
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"✅ Quality report written: {report_path}")
    return 0


def _cmd_status(args: argparse.Namespace, orchestrator: IObservabilityAggregate) -> int:
    """Show the current status file contents and metrics snapshot."""
    json_output = bool(getattr(args, "json", False))

    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_LOG
    from modules.shared.src.common.utility_core_path_validation import _get_workspace_root
    from modules.shared.src.common.utility_core_status import status_path_for

    status_path = status_path_for(DEFAULT_LOG)

    # Validate that the status file path is within the workspace root
    # (not a fixed DEFAULT_LOG path, since the log location may be configured)
    workspace_root = _get_workspace_root()
    try:
        status_path_resolved = status_path.resolve()
        status_path_resolved.relative_to(workspace_root)
    except (OSError, ValueError):
        error = {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": "Status file path is outside the workspace root",
            "hint": f"Status file must be under {workspace_root}",
            "field": "status_file",
        }
        return _fail_json(error["message"], "cli-400", json_output)

    status_map: dict[str, Any] | None = None
    if status_path.exists():
        try:
            status_map = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Invalid or unreadable status file - treat as absent
            status_map = None

    snapshot: MetricsSnapshot | None = None
    response = orchestrator.execute(ObservabilityRequest(verb="metrics_snapshot"))
    # A non-Snapshot payload (e.g. a mock in tests, or a future verb shape)
    # must not crash the status rendering — degrade to "no metrics".
    if response.success and isinstance(response.metrics, MetricsSnapshot):
        snapshot = response.metrics

    if json_output:
        payload: dict[str, Any] = {"success": True, "status_path": str(status_path)}
        if status_map:
            payload["status"] = status_map
        if snapshot is not None:
            payload["metrics"] = {
                "total_executions": snapshot.total_executions,
                "successful_executions": snapshot.successful_executions,
                "success_rate": snapshot.success_rate,
                "counters": dict(snapshot.counters),
            }
        print(json.dumps(payload, indent=2, default=str))
    else:
        print("📊 Observability Status")
        print("─" * 50)
        print(f"Status file: {status_path}")
        if status_map:
            for key, value in status_map.items():
                print(f"  {key:<20}: {value}")
        else:
            print("  (no status file present — no run in flight)")
        if snapshot is not None:
            print("\nMetrics snapshot:")
            print(f"  Total executions:      {snapshot.total_executions}")
            print(f"  Successful executions: {snapshot.successful_executions}")
            if snapshot.success_rate is not None:
                print(f"  Success rate:          {snapshot.success_rate:.1%}")
            for key, value in sorted(snapshot.counters.items()):
                print(f"  {key:<24}: {value}")
        else:
            print("\nMetrics: (no metrics recorded this session)")
    return 0


def handle_observability_command(
    args: argparse.Namespace,
    orchestrator: IObservabilityAggregate,
) -> int:
    """Handle observability subcommand via the IObservabilityAggregate verbs."""
    # The observability subparser registers dest="observability_command";
    # prefer whichever attribute the parser actually set.
    command = getattr(args, "observability_command", getattr(args, "command", None))

    if command == "report":
        return _cmd_report(args, orchestrator)
    if command == "status":
        return _cmd_status(args, orchestrator)

    print("Use 'qwen-web-arwaky observability --help' for usage")
    return 1


__all__ = ["handle_observability_command"]
