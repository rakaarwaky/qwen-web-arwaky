"""Agent: prompt orchestrator (AES405).

Implements IPromptAggregate: the single aggregate entry point for the prompt
feature. A surface holds this one object and calls :meth:`execute` with a
``PromptRequest``; the orchestrator routes the request to the capability that
serves its verb, so no surface has to know which adapter owns which verb.
"""

from __future__ import annotations

from typing import cast

from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.contract_prompt_protocol import (
    IAttachmentPromptProtocol,
    IDirectPromptProtocol,
    IPromptFileProtocol,
    IRunCancelProtocol,
)
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse


class PromptOrchestrator(IPromptAggregate):
    """Route a prompt request to the capability that serves its verb.

    The three prompt adapters each serve one processing verb, so a surface
    that called them directly would have to branch on the verb itself.
    Holding all three here keeps that branch in one place: the surface
    sends a request and gets a response, and the orchestrator picks the
    adapter.

    ``request_cancel`` reaches the file and attachment pipelines because
    those are the two that can register one run-scoped cancel event; a
    direct prompt has no registry to stop. Both adapters register their
    runs with the one cancel registry injected here (the container wires
    the same instance into the orchestrator and both adapters, across the
    CLI, MCP, and TUI surfaces), so the aggregate cancels once through
    that registry and reports 1 when a pipeline stopped and 0 when the
    run was already terminal or never registered (FR-PROMPT-004). The
    adapters keep their own ``request_cancel`` for direct protocol
    callers, but the aggregate does not fan the event out to them — a
    second registry resolution through an adapter would hit the same
    entry and change nothing.

    Raises:
        QwenCliError: When a verb is added to ``PromptVerb`` without an
            adapter being wired for it here.
    """

    def __init__(
        self,
        direct: IDirectPromptProtocol,
        file_only: IPromptFileProtocol,
        attachment: IAttachmentPromptProtocol,
        cancel_registry: IRunCancelProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        """Hold the one adapter that serves each prompt verb.

        Args:
            direct: Serves ``process_direct_prompt`` and implements
                ``request_cancel`` for direct protocol callers; the
                aggregate itself never routes a cancel through it.
            file_only: Serves ``process_prompt_file_only`` and implements
                ``request_cancel`` for direct protocol callers; the aggregate
                cancels running pipelines only via ``cancel_registry``.
            attachment: Serves ``process_prompt_with_attachment`` and
                implements ``request_cancel`` for direct protocol callers;
                the aggregate cancels running pipelines only via
                ``cancel_registry``.
            cancel_registry: The one targeted-cancel registry the file and
                attachment adapters register their runs with; the
                aggregate resolves a cancel through this same instance, so
                a cancel reaches the run by its stable ID rather than by
                event identity.
            observability: Records the routed verb, so a surface that sees a
                failed response can tell which adapter produced it.
        """
        self._by_verb: dict[str, IPromptAggregate] = {
            "process_direct_prompt": cast(IPromptAggregate, direct),
            "process_prompt_file_only": cast(IPromptAggregate, file_only),
            "process_prompt_with_attachment": cast(IPromptAggregate, attachment),
        }
        self._cancel_registry = cancel_registry
        self._observability = observability

    def execute(self, request: PromptRequest) -> PromptResponse:
        """Route *request* to the adapter that serves its verb.

        Returns:
            PromptResponse: The adapter's response, unchanged, except for
            ``request_cancel`` which reports how many in-flight pipelines
            actually stopped.

        Raises:
            QwenCliError: When no adapter is wired for ``request.verb``.
        """
        if request.verb == "request_cancel":
            return self._cancel_running(request)
        adapter = self._by_verb.get(request.verb)
        if adapter is None:
            raise QwenCliError(f"No prompt adapter serves verb {request.verb!r}")
        return adapter.execute(request)

    def _cancel_running(self, request: PromptRequest) -> PromptResponse:
        """Stop the run held by ``request.cancel_event`` and count what stopped.

        The event resolves through the one shared registry the adapters
        also use, so a single ``cancel_by_event`` is the whole operation:
        it sets the run's event, closes the run's browser context, and
        answers whether an in-flight run was found. A run that already
        reached a terminal state (or was never registered) answers zero,
        and a cancel without an event is a no-op that reports zero.
        """
        cancel_event = request.cancel_event
        if cancel_event is None:
            return PromptResponse(cancelled=False, pipelines_stopped=0)
        stopped = bool(self._cancel_registry.cancel_by_event(cancel_event))
        return PromptResponse(cancelled=stopped, pipelines_stopped=1 if stopped else 0)


__all__ = ["PromptOrchestrator"]
