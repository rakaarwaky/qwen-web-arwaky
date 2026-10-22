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
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText

_CANCELLED = PromptResponse(cancelled=True, pipelines_stopped=1)


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


def test_smoke_a_cancellation_resolves_through_the_shared_registry() -> None:
    """``request_cancel`` resolves through the one shared cancel registry
    the adapters also use — a single ``cancel_by_event`` stops the run and
    reports whether a pipeline actually stopped. The adapters' own
    ``execute`` is never re-entered: the aggregate routes the cancel solely
    through the registry.
    """
    orchestrator, stubs = _orchestrator(
        response=PromptResponse(cancelled=True, pipelines_stopped=1),
    )
    stubs["cancel_registry"].cancel_by_event.return_value = True

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    stubs["cancel_registry"].cancel_by_event.assert_called_once()
    stubs["process_prompt_file_only"].execute.assert_not_called()
    stubs["process_prompt_with_attachment"].execute.assert_not_called()
    assert response.cancelled is True
    assert response.pipelines_stopped == 1


def test_smoke_a_cancel_with_no_active_pipeline_reports_zero() -> None:
    """A cancel for a run that already reached a terminal state reports
    zero stopped pipelines instead of a blanket success (FR-PROMPT-004)."""
    orchestrator, stubs = _orchestrator()
    stubs["cancel_registry"].cancel_by_event.return_value = False

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    stubs["cancel_registry"].cancel_by_event.assert_called_once()
    assert response.cancelled is False
    assert response.pipelines_stopped == 0


def test_smoke_a_cancel_without_an_event_is_a_zero_no_op() -> None:
    """A cancel request carrying no event stops nothing and reports zero."""
    orchestrator, _ = _orchestrator()

    response = orchestrator.execute(PromptRequest(verb="request_cancel"))

    assert response.cancelled is False
    assert response.pipelines_stopped == 0


def test_smoke_a_verb_with_no_wired_adapter_is_refused_by_name() -> None:
    """An unwired verb is a wiring bug, so it is raised rather than
    silently answered with an empty response.
    """
    orchestrator, _ = _orchestrator()

    with pytest.raises(QwenCliError):
        orchestrator.execute(PromptRequest(verb="teleport"))
