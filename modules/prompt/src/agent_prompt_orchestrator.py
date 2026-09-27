"""Agent: prompt orchestrator (AES405).

Implements IPromptAggregate: the single aggregate entry point for the prompt
feature. A surface holds this one object and calls :meth:`execute` with a
``PromptRequest``; the orchestrator routes the request to the capability that
serves its verb, so no surface has to know which adapter owns which verb.
"""

from __future__ import annotations

from modules.shared.src.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse


class PromptOrchestrator(IPromptAggregate):
    """Route a prompt request to the capability that serves its verb.

    The three prompt adapters each serve one processing verb, so a surface
    that called them directly would have to branch on the verb itself.
    Holding all three here keeps that branch in one place: the surface
    sends a request and gets a response, and the orchestrator picks the
    adapter.

    ``request_cancel`` reaches the file and attachment pipelines because
    those are the two that register a run-scoped cancel event; a direct
    prompt has no registry to stop. It is fanned out to both so a
    cancelling surface does not have to know which pipeline it started.

    Raises:
        QwenCliError: When a verb is added to ``PromptVerb`` without an
            adapter being wired for it here.
    """

    def __init__(self, direct: IPromptAggregate, file_only: IPromptAggregate, attachment: IPromptAggregate) -> None:
        """Hold the one adapter that serves each verb.

        Args:
            direct: Serves ``process_direct_prompt``.
            file_only: Serves ``process_prompt_file_only`` and ``request_cancel``.
            attachment: Serves ``process_prompt_with_attachment`` and ``request_cancel``.
        """
        self._by_verb: dict[str, IPromptAggregate] = {
            "process_direct_prompt": direct,
            "process_prompt_file_only": file_only,
            "process_prompt_with_attachment": attachment,
        }
        self._cancellable = (file_only, attachment)

    def execute(self, request: PromptRequest) -> PromptResponse:
        """Route *request* to the adapter that serves its verb.

        Returns:
            PromptResponse: The adapter's response, unchanged, except for
            ``request_cancel`` which reports which pipelines stopped.

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
        """Stop the run held by ``request.cancel_event`` in every pipeline that registered it."""
        cancel_event = request.cancel_event
        if cancel_event is None:
            return PromptResponse(cancelled=False)
        for adapter in self._cancellable:
            adapter.execute(request)
        return PromptResponse(cancelled=True)


__all__ = ["PromptOrchestrator"]
