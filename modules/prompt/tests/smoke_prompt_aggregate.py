"""Smoke tests for the prompt aggregate.

The aggregate's promise is that both entry runtimes reach a prompt verb
through one door, and that a surface never has to branch on the verb
itself. These drive that door with a stub adapter per pipeline.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.agent_prompt_orchestrator import PromptOrchestrator
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText

_CANCELLED = PromptResponse(cancelled=True)


def _orchestrator(
    response: PromptResponse | None = None,
) -> tuple[PromptOrchestrator, dict[str, MagicMock]]:
    """Return the aggregate wired to one stub per pipeline, and the stubs."""
    answer = response or PromptResponse(response_text=ResponseText("The answer"))
    stubs = {
        "process_direct_prompt": MagicMock(),
        "process_prompt_file_only": MagicMock(),
        "process_prompt_with_attachment": MagicMock(),
        "cancel_registry": MagicMock(),
        "observability": MagicMock(),
    }
    for stub in stubs.values():
        stub.execute.return_value = answer
    cancellables = [stubs["process_prompt_file_only"], stubs["process_prompt_with_attachment"]]
    for stub in cancellables:
        stub.execute.return_value = _CANCELLED
    return (
        PromptOrchestrator(
            direct=stubs["process_direct_prompt"],
            file_only=stubs["process_prompt_file_only"],
            attachment=stubs["process_prompt_with_attachment"],
            cancel_registry=stubs["cancel_registry"],
            observability=stubs["observability"],
        ),
        stubs,
    )


def test_smoke_a_direct_prompt_routes_to_the_direct_adapter() -> None:
    orchestrator, stubs = _orchestrator()

    orchestrator.execute(PromptRequest(verb="process_direct_prompt", prompt_file="prompt.md"))

    stubs["process_direct_prompt"].execute.assert_called_once()


def test_smoke_a_file_prompt_routes_to_the_file_adapter() -> None:
    orchestrator, stubs = _orchestrator()

    orchestrator.execute(PromptRequest(verb="process_prompt_file_only"))

    stubs["process_prompt_file_only"].execute.assert_called_once()


def test_smoke_an_attachment_prompt_routes_to_the_attachment_adapter() -> None:
    orchestrator, stubs = _orchestrator()

    orchestrator.execute(PromptRequest(verb="process_prompt_with_attachment"))

    stubs["process_prompt_with_attachment"].execute.assert_called_once()


def test_smoke_the_answer_comes_back_as_response_text() -> None:
    orchestrator, _ = _orchestrator()

    response = orchestrator.execute(PromptRequest(verb="process_direct_prompt", prompt_file="prompt.md"))

    assert str(response.response_text) == "The answer"


def test_smoke_a_cancellation_reaches_both_registered_pipelines() -> None:
    """``request_cancel`` is fanned out to the file and attachment
    pipelines, because a direct prompt has no run to cancel.
    """
    orchestrator, stubs = _orchestrator()

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    stubs["process_prompt_file_only"].execute.assert_called_once()
    stubs["process_prompt_with_attachment"].execute.assert_called_once()
    assert response.cancelled is True


def test_smoke_a_verb_with_no_wired_adapter_is_refused_by_name() -> None:
    """An unwired verb is a wiring bug, so it is raised rather than
    silently answered with an empty response.
    """
    orchestrator, _ = _orchestrator()

    with pytest.raises(QwenCliError):
        orchestrator.execute(PromptRequest(verb="teleport"))
