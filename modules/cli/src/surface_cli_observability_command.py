"""CLI surface: observability command — query run metrics and quality reports.

Smart surface: maps parsed args to the IObservabilityAggregate verbs
(write_quality_report, write_status) and formats the response as a
human-readable summary or JSON envelope. Exposes the LoggingOrchestrator
and MetricsCounter capability so operators can inspect run outcomes without
relying on the interactive TUI.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from typing import Any

from modules.shared.src.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.taxonomy_logging_vo import ObservabilityRequest


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


def _cmd_status(args: argparse.Namespace, metrics: Any) -> int:
    """Show the current status file contents and metrics snapshot."""
    json_output = bool(getattr(args, "json", False))

    from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
    from modules.shared.src.utility_core_status import status_path_for

    status_path = status_path_for(DEFAULT_LOG)
    status_map: dict[str, Any] | None = None
    if status_path.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            status_map = json.loads(status_path.read_text(encoding="utf-8"))

    metrics_snapshot = metrics.snapshot() if metrics is not None else None

    if json_output:
        payload: dict[str, Any] = {"success": True, "status_path": str(status_path), "status": status_map}
        if metrics_snapshot is not None:
            payload["metrics"] = {
                "counters": metrics_snapshot.counters,
                "total_executions": metrics_snapshot.total_executions,
                "successful_executions": metrics_snapshot.successful_executions,
                "success_rate": metrics_snapshot.success_rate,
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
        if metrics_snapshot is not None:
            print("\nMetrics snapshot:")
            print(f"  Total executions:      {metrics_snapshot.total_executions}")
            print(f"  Successful executions: {metrics_snapshot.successful_executions}")
            if metrics_snapshot.success_rate is not None:
                print(f"  Success rate:          {metrics_snapshot.success_rate:.1%}")
            for key, value in sorted(metrics_snapshot.counters.items()):
                print(f"  {key:<24}: {value}")
        else:
            print("\nMetrics: (no metrics recorded this session)")
    return 0


def handle(args: argparse.Namespace, orchestrator: IObservabilityAggregate, metrics: Any = None) -> int:
    """Dispatch the observability subcommand to the matching handler."""
    verb = getattr(args, "observability_command", None)
    if verb == "report":
        return _cmd_report(args, orchestrator)
    if verb == "status":
        if metrics is None:
            print("[ERROR] Metrics not available.", file=sys.stderr)
            return 1
        return _cmd_status(args, metrics)
    print("Use 'qwen-web-arwaky observability --help' for usage")
    return 1


__all__ = ["handle"]
