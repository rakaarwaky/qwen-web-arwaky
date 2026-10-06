"""Prompt-domain aggregate contracts (AES101 `_aggregate`).

One file for the prompt feature. Each class below is one aggregate: the
single entry point the surface/root/CLI/MCP layer calls for that concern.
An aggregate carries exactly one method — the door consumers knock on — so
adding a consumer verb means adding a variant to the request VO, never a
second aggregate method.

Aggregates:

- ``IPromptAggregate``   → ``PromptOrchestrator``  (direct / file / attachment)

The shared inject → send → wait flow is a capability seam in
``contract_prompt_protocol.py`` (``IPromptFlowProtocol`` → ``PromptFlowDispatcher``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse


class IPromptAggregate(ABC):
    """Single entry point over the prompt feature.

    Consumers pass a request; the agent behind the aggregate dispatches
    to the appropriate protocol operation. Adding a consumer verb means
    adding a variant to ``PromptRequest``, not adding an aggregate method.
    """

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run one prompt operation and return the result."""
        ...


__all__ = ["IPromptAggregate"]

_layer_symbols = {
    "IPromptAggregate": IPromptAggregate,
}
