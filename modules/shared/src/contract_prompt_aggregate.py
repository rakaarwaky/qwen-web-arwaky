"""Prompt-domain aggregate contract (AES101 `_aggregate`).

``IPromptAggregate`` is the single entry point over the prompt feature.
The CLI/MCP/surface callers pass a ``PromptRequest``; the agent behind
the aggregate routes internally to the rich protocol methods:

- ``inject_text``     → prompt injection / find_input
- ``click_send``       → send / count_messages / latest_message
- ``wait_for_response`` → stream wait / completion / thinking checks
- ``write_output``      → output persistence
- ``upload_attachment`` → attachment upload / validation
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

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IPromptAggregate": IPromptAggregate,
}
