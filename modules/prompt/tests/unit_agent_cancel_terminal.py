"""Acceptance: a cancel reports how many pipelines actually stopped.

FR-PROMPT-004 / PROMPT-02: cancel output is "the number of pipelines that
stopped", and a pipeline that already reached a terminal state is not
reported as stopped. These pin the aggregate's count, the registry's
stopped flag, and the sibling-isolation rule the TUI slot model relies on.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.agent_prompt_orchestrator import PromptOrchestrator
from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter
from modules.prompt.src.capabilities_prompt_file_adapter import PromptFileAdapter
from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.shared.src.common.taxonomy_core_vo import RunState
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse


def _make_file_adapter(cancel: CapabilitiesRunCancelRegistry) -> PromptFileAdapter:
    return PromptFileAdapter(*(MagicMock() for _ in range(9)), cancel=cancel)


def _make_attachment_adapter(cancel: CapabilitiesRunCancelRegistry) -> AttachmentPromptAdapter:
    return AttachmentPromptAdapter(*(MagicMock() for _ in range(11)), cancel=cancel)


def _orchestrator(
    cancel: CapabilitiesRunCancelRegistry,
) -> tuple[PromptOrchestrator, PromptFileAdapter, AttachmentPromptAdapter]:
    file_adapter = _make_file_adapter(cancel)
    attachment_adapter = _make_attachment_adapter(cancel)
    return (
        PromptOrchestrator(
            direct=MagicMock(),
            file_only=file_adapter,
            attachment=attachment_adapter,
            cancel_registry=cancel,
            observability=MagicMock(),
        ),
        file_adapter,
        attachment_adapter,
    )


def _registered_run(cancel: CapabilitiesRunCancelRegistry, bctx: object | None = None) -> RunState:
    run_state = RunState(cancel_event=threading.Event(), active_bctx=bctx)
    cancel.register(run_state)
    return run_state


def test_cancel_on_an_in_flight_file_pipeline_reports_one_stopped_pipeline() -> None:
    """FR-PROMPT-004: one live pipeline, one stopped pipeline."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)
    run_state = _registered_run(cancel, bctx=MagicMock())

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=run_state.cancel_event))

    assert response.pipelines_stopped == 1
    assert response.cancelled is True
    assert run_state.cancel_event.is_set()


def test_cancel_on_a_terminal_pipeline_reports_zero() -> None:
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)
    run_state = _registered_run(cancel)
    cancel.release(run_state)

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=run_state.cancel_event))

    assert response.pipelines_stopped == 0
    assert response.cancelled is False


def test_cancel_on_one_pipeline_leaves_the_sibling_run_alone() -> None:
    """FR-PROMPT-005: cancelling one run never touches a sibling's event or context."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)
    first = _registered_run(cancel, bctx=MagicMock())
    second = _registered_run(cancel, bctx=MagicMock())

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=first.cancel_event))

    assert response.pipelines_stopped == 1
    assert first.cancel_event.is_set()
    assert not second.cancel_event.is_set()


def test_cancel_without_an_event_reports_zero_without_error() -> None:
    """A cancel request carrying no event stops nothing and raises nothing."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)

    response = orchestrator.execute(PromptRequest(verb="request_cancel"))

    assert response.pipelines_stopped == 0
    assert response.cancelled is False


def test_cancel_with_an_unregistered_event_reports_zero_without_error() -> None:
    """FR-PROMPT-004 error handling: an event nothing registered surfaces no error."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    assert response.pipelines_stopped == 0
    assert response.cancelled is False


@pytest.mark.parametrize("factory", [_make_file_adapter, _make_attachment_adapter], ids=["file", "attachment"])
def test_each_adapter_reports_its_own_stopped_flag(factory) -> None:
    """Each adapter's typed request_cancel answers honestly for direct protocol callers.

    The aggregate itself cancels once through the shared registry; these
    per-adapter seams stay for callers that hold an adapter directly.
    """
    cancel = CapabilitiesRunCancelRegistry()
    adapter = factory(cancel)
    run_state = _registered_run(cancel, bctx=MagicMock())

    response = adapter.execute(PromptRequest(verb="request_cancel", cancel_event=run_state.cancel_event))

    assert response.pipelines_stopped == 1
    assert response.cancelled is True
    assert run_state.cancel_event.is_set()


@pytest.mark.parametrize("factory", [_make_file_adapter, _make_attachment_adapter], ids=["file", "attachment"])
def test_each_adapter_reports_zero_for_a_terminal_run(factory) -> None:
    cancel = CapabilitiesRunCancelRegistry()
    adapter = factory(cancel)
    run_state = _registered_run(cancel)
    cancel.release(run_state)

    response = adapter.execute(PromptRequest(verb="request_cancel", cancel_event=run_state.cancel_event))

    assert response.pipelines_stopped == 0
    assert response.cancelled is False


def test_a_direct_prompt_reports_zero_stopped_pipelines() -> None:
    """FR-PROMPT-004 business rule: a direct prompt has no cancel registry."""
    from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter

    direct = DirectPromptAdapter(
        browser_lifecycle=MagicMock(),
        browser_navigation=MagicMock(),
        browser_diagnostics=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(),
        flow=MagicMock(),
    )

    response = direct.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    assert response.pipelines_stopped == 0
    assert response.cancelled is False
    assert response.response_text is None


def test_terminal_and_active_runs_share_one_event_index_safely() -> None:
    """BE-3-002: a slot reuses its event across sequential jobs.

    Registering B with the same event supersedes A's event-index mapping, so
    releasing A must not delete B's entry — B stays cancellable.
    """
    cancel = CapabilitiesRunCancelRegistry()
    event = threading.Event()
    state_a = RunState(cancel_event=event)
    cancel.register(state_a)
    state_b = RunState(cancel_event=event, active_bctx=MagicMock())
    cancel.register(state_b)

    cancel.release(state_a)

    assert cancel.cancel_by_event(event) is True
    assert state_b.cancel_event.is_set()
    # The finished run stays finished: cancel is a no-op for it.
    assert cancel.cancel_run(state_a.run_id) is False


def test_release_never_removes_an_event_index_entry_owned_by_another_run() -> None:
    cancel = CapabilitiesRunCancelRegistry()
    event = threading.Event()
    first = RunState(cancel_event=event)
    second = RunState(cancel_event=event)
    cancel.register(first)
    cancel.register(second)

    cancel.release(first)
    cancel.release(second)

    assert cancel.cancel_by_event(event) is False


def test_swarm_cancel_runner_forwards_the_event_through_the_aggregate() -> None:
    """The seam the Swarm cancel runner calls still resolves through the aggregate."""
    from modules.swarm.src.capabilities_swarm_cancel import SwarmCancelRunner

    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)
    runner = SwarmCancelRunner(registry=MagicMock(), attachment=orchestrator)
    run_state = _registered_run(cancel, bctx=MagicMock())

    runner._request_attachment_cancel(run_state.cancel_event)

    assert run_state.cancel_event.is_set()


def test_pipeline_stopped_count_is_not_a_blind_success() -> None:
    """The old defect: fan-out returned cancelled=True unconditionally. Pin that it cannot."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator, _file, _attachment = _orchestrator(cancel)

    response = orchestrator.execute(PromptRequest(verb="request_cancel", cancel_event=threading.Event()))

    assert isinstance(response, PromptResponse)
    assert response.cancelled is False
