"""Unit tests for the observability CLI surface (surface_cli_observability_command)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_observability_command import handle as handle_observability_command
from modules.shared.src.taxonomy_logging_vo import MetricsSnapshot


def _status_args(json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.observability_command = "status"
    args.json = json_output
    return args


def _report_args(json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.observability_command = "report"
    args.json = json_output
    return args


def _metrics_mock(snapshot: MetricsSnapshot) -> MagicMock:
    """Mock an IMetricsProtocol whose snapshot() returns the dict form the contract defines."""
    metrics = MagicMock()
    metrics.snapshot.return_value = {
        "counters": snapshot.counters,
        "total_executions": snapshot.total_executions,
        "successful_executions": snapshot.successful_executions,
        "success_rate": snapshot.success_rate,
    }
    return metrics


class TestObservabilityReport:
    def test_report_success_prints_the_path(self, capsys) -> None:
        orchestrator = MagicMock()
        orchestrator.execute.return_value = MagicMock(success=True, report_path=Path("/tmp/report.json"))
        rc = handle_observability_command(_report_args(), orchestrator)
        assert rc == 0
        assert "Quality report written" in capsys.readouterr().out

    def test_report_failure_returns_nonzero(self, capsys) -> None:
        orchestrator = MagicMock()
        orchestrator.execute.return_value = MagicMock(success=False, error="no run")
        rc = handle_observability_command(_report_args(), orchestrator)
        assert rc == 1
        assert "no run" in capsys.readouterr().err

    def test_report_json_envelope(self, capsys) -> None:
        orchestrator = MagicMock()
        orchestrator.execute.return_value = MagicMock(success=True, report_path=Path("/tmp/report.json"))
        rc = handle_observability_command(_report_args(json_output=True), orchestrator)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert "report.json" in payload["report_path"]


class TestObservabilityStatus:
    def test_status_without_metrics_falls_back_to_status_file(self, capsys) -> None:
        # metrics=None is a valid runtime state; the surface degrades
        # gracefully to the status file rather than erroring out.
        rc = handle_observability_command(_status_args(), MagicMock(), None)
        assert rc == 0
        out = capsys.readouterr().out
        assert "no metrics recorded" in out

    def test_status_reports_the_metrics_snapshot(self, capsys) -> None:
        snapshot = MetricsSnapshot(
            counters={"run_count": 5},
            total_executions=5,
            successful_executions=4,
            success_rate=0.8,
        )
        rc = handle_observability_command(_status_args(), MagicMock(), _metrics_mock(snapshot))
        assert rc == 0
        out = capsys.readouterr().out
        assert "Total executions" in out
        assert "4" in out

    def test_status_json_envelope_carries_metrics(self, capsys) -> None:
        snapshot = MetricsSnapshot(counters={}, total_executions=0, successful_executions=0, success_rate=None)
        rc = handle_observability_command(_status_args(json_output=True), MagicMock(), _metrics_mock(snapshot))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["metrics"]["total_executions"] == 0

    def test_status_reads_the_status_file_when_present(self, tmp_path, capsys) -> None:
        status_file = tmp_path / "status.json"
        status_file.write_text(json.dumps({"state": "idle"}), encoding="utf-8")
        snapshot = MetricsSnapshot()
        # status_path_for is imported inside _cmd_status; patch the source module.
        with (
            patch("modules.shared.src.utility_core_status.status_path_for", return_value=status_file),
        ):
            rc = handle_observability_command(_status_args(), MagicMock(), _metrics_mock(snapshot))
        assert rc == 0
        out = capsys.readouterr().out
        assert "idle" in out

    def test_status_invalid_json_falls_back_gracefully(self, tmp_path, capsys) -> None:
        """A status.json containing malformed JSON is skipped, not raised (Issue 14)."""
        status_file = tmp_path / "status.json"
        status_file.write_text("{not valid json", encoding="utf-8")
        snapshot = MetricsSnapshot()
        with (
            patch("modules.shared.src.utility_core_status.status_path_for", return_value=status_file),
        ):
            rc = handle_observability_command(_status_args(), MagicMock(), _metrics_mock(snapshot))
        assert rc == 0
        out = capsys.readouterr().out
        # Invalid JSON means status_map stays None; the output falls back to
        # the "no status file present" message path (status_map is falsy).
        assert "no status file present" in out or "state" not in out

    def test_status_double_absent(self, capsys) -> None:
        """metrics=None and no status file: both sections report their absence (Issue 15)."""
        with (
            patch(
                "modules.shared.src.utility_core_status.status_path_for", return_value=Path("/nonexistent/status.json")
            ),
        ):
            rc = handle_observability_command(_status_args(), MagicMock(), None)
        assert rc == 0
        out = capsys.readouterr().out
        assert "no status file present" in out
        assert "no metrics recorded" in out


class TestObservabilityDispatch:
    def test_unknown_verb_returns_usage(self, capsys) -> None:
        args = MagicMock()
        args.observability_command = "bogus"
        rc = handle_observability_command(args, MagicMock())
        assert rc == 1
        assert "--help" in capsys.readouterr().out
