"""Prompt-runtime aggregate contract (AES101 `_aggregate`).

One file for the prompt_runtime feature. Each class below is one
aggregate: the single entry point the surface/root/CLI/MCP layer calls
for that concern. An aggregate carries exactly one method — the door
consumers knock on — so adding a consumer verb means adding a variant to
the request VO, never a second aggregate method.

Aggregates:

- ``IPromptRuntimeAggregate`` → ``PromptRuntimeOrchestrator``
  (inject / send / watch / upload / persist)

The door sits over the five runtime capability seams
(``IInjectionProtocol``, ``ISendProtocol``, ``IStreamProtocol``,
``IUploadProtocol``, ``ISaverProtocol`` in
``modules/shared/src/prompt/contract_prompt_protocol.py``, implemented
by ``modules/prompt_runtime/src/``). It never re-routes the
inject → send → wait prompt pipeline — that sequencing belongs to
``IPromptAggregate`` in ``modules/prompt`` and the shared flow
dispatcher behind it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest, RuntimeResponse


class IPromptRuntimeAggregate(ABC):
    """Single entry point over the prompt-runtime feature.

    This aggregate's door is the routing facade over the five runtime
    capabilities: a consumer passes a ``RuntimeRequest`` naming one verb
    (``inject``, ``send``, ``watch``, ``upload``, ``persist``) and the
    agent behind it dispatches to the capability method that serves that
    verb. Each of those verbs exists exactly once — as a variant on
    ``RuntimeRequest``, never as a second method here — so the surface
    layer keeps one stable call shape while the feature grows.
    """

    @abstractmethod
    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        """Run one runtime verb through its capability and return the result."""
        ...


__all__ = ["IPromptRuntimeAggregate"]

_layer_symbols = {
    "IPromptRuntimeAggregate": IPromptRuntimeAggregate,
}
