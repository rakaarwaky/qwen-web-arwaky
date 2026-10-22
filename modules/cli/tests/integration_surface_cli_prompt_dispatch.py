"""Regression test: headless prompt dispatch must drive one prompt aggregate.

``_dispatch`` used to pass the three bare prompt adapters positionally to
``handle_run_command`` while ``handle`` takes a single ``IPromptAggregate``,
so every non-interactive ``prompt {direct,file,attach}`` run raised
``TypeError``. The three subcommands must now route through one composed
``PromptOrchestrator`` and return a surface envelope — success or a
domain failure — never an unhandled exception.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.root_cli_main_entry import _build_config, _dispatch
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse, PromptVerb

#: ``ResponseText`` is a transparent NewType over ``str``.
PromptResponseText = str


class _RecordingAggregate(IPromptAggregate):
    """Prompt aggregate double that records the routed verb and answers flat."""

    def __init__(self, answer: str = "answer text") -> None:
        self._answer = answer
        self.calls: list[PromptRequest] = []

    def execute(self, request: PromptRequest) -> PromptResponse:
        self.calls.append(request)
        return PromptResponse(response_text=PromptResponseText(self._answer))


def _container(aggregate: IPromptAggregate) -> MagicMock:
    container = MagicMock()
    container.config = MagicMock()
    container.observability = MagicMock()
    container.session_manager = MagicMock()
    container.session_manager.load_pool.return_value = MagicMock(total_count=0, sessions=[])
    container.session_rotator = MagicMock()
    # The prompt composition reads these four seams off the container.
    container.agent_direct_prompt_orchestrator = aggregate
    container.agent_prompt_file_orchestrator = aggregate
    container.agent_attachment_prompt_orchestrator = aggregate
    container.run_cancel_registry = MagicMock()
    return container


def _args(prompt_command: str, tmp_path: Path) -> argparse.Namespace:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("body", encoding="utf-8")
    attachment = tmp_path / "att.txt"
    attachment.write_text("data", encoding="utf-8")
    return argparse.Namespace(
        action="prompt",
        prompt_command=prompt_command,
        headless=True,
        verbose=False,
        model=None,
        output_path=str(tmp_path / "out.md"),
        text="hello qwen",
        prompt_path=str(prompt_file),
        # `prompt file` must not carry an attachment: `single` mode routes to
        # the attachment verb whenever cfg.file_path is set.
        attachment_path=str(attachment) if prompt_command == "attach" else None,
    )


def _dispatch_prompt(prompt_command: str, tmp_path: Path, aggregate: IPromptAggregate) -> int:
    args = _args(prompt_command, tmp_path)
    cfg = _build_config(args)
    with (
        patch("modules.root_cli_main_entry._default_container") as container_fn,
        patch("sys.argv", ["qwen-web-arwaky", "prompt", prompt_command]),
        patch("modules.root_cli_main_entry._result_exit_code", return_value=0),
    ):
        container_fn.return_value = _container(aggregate)
        return _dispatch(container_fn.return_value, ["prompt", prompt_command], args, cfg)


@pytest.mark.parametrize(
    "prompt_command,verb",
    [
        ("direct", "process_direct_prompt"),
        ("file", "process_prompt_file_only"),
        ("attach", "process_prompt_with_attachment"),
    ],
)
def test_headless_prompt_subcommand_routes_through_one_aggregate(
    prompt_command: str, verb: PromptVerb, tmp_path: Path
) -> None:
    """Each subcommand must reach the composed aggregate, not raise TypeError."""
    aggregate = _RecordingAggregate()

    assert _dispatch_prompt(prompt_command, tmp_path, aggregate) == 0
    assert [c.verb for c in aggregate.calls] == [verb]


def test_headless_prompt_dispatch_reports_domain_failure_without_raising(tmp_path: Path) -> None:
    """A failure the aggregate raises must come back as an envelope, not a traceback."""

    class _Failing(IPromptAggregate):
        def execute(self, request: PromptRequest) -> PromptResponse:
            raise RuntimeError("browser launch refused")

    args = _args("file", tmp_path)
    cfg = _build_config(args)
    captured: dict[str, Any] = {}

    def _exit_code(result: dict[str, object], json_output: bool = False) -> int:
        captured.update(result)
        return 1

    with (
        patch("modules.root_cli_main_entry._default_container") as container_fn,
        patch("sys.argv", ["qwen-web-arwaky", "prompt", "file"]),
        patch("modules.root_cli_main_entry._result_exit_code", side_effect=_exit_code),
    ):
        container_fn.return_value = _container(_Failing())
        code = _dispatch(container_fn.return_value, ["prompt", "file"], args, cfg)

    assert code == 1
    assert captured.get("success") is False
