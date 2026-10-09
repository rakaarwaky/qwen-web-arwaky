"""Unit tests for the swarm CLI surface (surface_cli_swarm_command)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_swarm_command import handle as handle_swarm_command
from modules.shared.src.taxonomy_swarm_vo import (
    SwarmAgentSnapshot,
    SwarmRequest,
    SwarmSnapshot,
)


def _snapshot(status: str = "running", agents: tuple[SwarmAgentSnapshot, ...] = ()) -> SwarmSnapshot:
    return SwarmSnapshot(
        swarm_id="swarm-1",
        input_path=Path("/tmp/in"),
        root_path=Path("/tmp/out"),
        status=status,
        max_attempts=3,
        browser_concurrency=2,
        agents=agents,
    )


def _start_args(input_path: Path, json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.swarm_command = "start"
    args.input = str(input_path)
    args.json = json_output
    return args


def _status_args(swarm_id: str = "swarm-1", json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.swarm_command = "status"
    args.swarm_id = swarm_id
    args.json = json_output
    return args


def _cancel_args(swarm_id: str = "swarm-1", json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.swarm_command = "cancel"
    args.swarm_id = swarm_id
    args.json = json_output
    return args


class TestSwarmStart:
    def test_missing_input_is_refused(self, tmp_path, capsys) -> None:
        missing = tmp_path / "does-not-exist"
        rc = handle_swarm_command(_start_args(missing), MagicMock())
        assert rc == 1
        assert "Swarm input not found" in capsys.readouterr().err

    def test_start_uses_the_start_verb_and_reports(self, tmp_path, capsys) -> None:
        (tmp_path / "input.md").write_text("task")
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=_snapshot("running"), error=None)
        rc = handle_swarm_command(_start_args(tmp_path / "input.md"), swarm)
        assert rc == 0
        request = swarm.execute.call_args[0][0]
        assert isinstance(request, SwarmRequest)
        assert request.verb == "start"
        out = capsys.readouterr().out
        assert "swarm-1" in out
        assert "swarm status" in out

    def test_start_orm_error_returns_nonzero(self, tmp_path, capsys) -> None:
        (tmp_path / "input.md").write_text("task")
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=None, error="no sessions")
        rc = handle_swarm_command(_start_args(tmp_path / "input.md"), swarm)
        assert rc == 1
        assert "no sessions" in capsys.readouterr().err

    def test_start_json_envelope(self, tmp_path, capsys) -> None:
        (tmp_path / "input.md").write_text("task")
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=_snapshot("running"), error=None)
        rc = handle_swarm_command(_start_args(tmp_path / "input.md", json_output=True), swarm)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["swarm_id"] == "swarm-1"
        assert payload["status"] == "running"


class TestSwarmStatus:
    def test_status_uses_the_snapshot_verb(self, capsys) -> None:
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=_snapshot("completed"), error=None)
        rc = handle_swarm_command(_status_args(), swarm)
        assert rc == 0
        assert swarm.execute.call_args[0][0].verb == "snapshot"
        assert "swarm-1" in capsys.readouterr().out

    def test_status_unknown_swarm_returns_nonzero(self, capsys) -> None:
        swarm = MagicMock()
        # No error flag, but no snapshot either: the surface reports the missing
        # id rather than surfacing an upstream error.
        swarm.execute.return_value = MagicMock(snapshot=None, error=None)
        rc = handle_swarm_command(_status_args(), swarm)
        assert rc == 1
        assert "No Swarm found" in capsys.readouterr().err

    def test_status_json_envelope(self, capsys) -> None:
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=_snapshot("completed"), error=None)
        rc = handle_swarm_command(_status_args(json_output=True), swarm)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["swarm_id"] == "swarm-1"


class TestSwarmCancel:
    def test_cancel_uses_the_cancel_verb(self, capsys) -> None:
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=_snapshot("cancelled"), error=None)
        rc = handle_swarm_command(_cancel_args(), swarm)
        assert rc == 0
        assert swarm.execute.call_args[0][0].verb == "cancel"
        assert "cancelled" in capsys.readouterr().out

    def test_cancel_failure_returns_nonzero(self, capsys) -> None:
        swarm = MagicMock()
        swarm.execute.return_value = MagicMock(snapshot=None, error="locked")
        rc = handle_swarm_command(_cancel_args(), swarm)
        assert rc == 1
        assert "locked" in capsys.readouterr().err


class TestSwarmDispatch:
    def test_unknown_verb_returns_usage(self, capsys) -> None:
        args = MagicMock()
        args.swarm_command = "bogus"
        rc = handle_swarm_command(args, MagicMock())
        assert rc == 1
        assert "--help" in capsys.readouterr().out
