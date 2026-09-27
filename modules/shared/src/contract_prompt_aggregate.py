"""Prompt-domain aggregate contracts (AES101 `_aggregate`).

One file for the prompt feature. Each class below is one aggregate: the
single entry point the surface/root/CLI/MCP layer calls for that concern.
An aggregate carries exactly one method — the door consumers knock on — so
adding a consumer verb means adding a variant to the request VO, never a
second aggregate method.

Aggregates:

- ``IPromptAggregate``   → ``PromptOrchestrator``  (direct / file / attachment)
- ``IPromptFlowAggregate`` → ``SharedFlowOrchestrator`` (inject → send → wait)

Capability seams (protocols) are in ``contract_core_protocol.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    MessageCount,
    SenderConfig,
)
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


class IPromptFlowAggregate(ABC):
    """Aggregate contract for the shared prompt dispatch/response-wait flow.

    Implemented by the shared flow orchestrator and consumed by the direct,
    file, and attachment prompt adapters via dependency injection
    (agent-to-agent communication through a contract aggregate).
    """

    @abstractmethod
    def dispatch_and_wait_for_response(
        self,
        page: Page,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        observability: IObservabilityProtocol,
        filepath: Path,
        prompt: str,
        msg_count_before: MessageCount,
        timeout_sec: int,
        active_cfg: AppConfig,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
        cancel_event: Any | None = None,
    ) -> str:
        """Inject prompt, click send, and wait for the AI response.

        ``cancel_event`` is an optional ``threading.Event`` created per-run;
        when set, the flow raises ``RunCancelledError`` so the caller's
        browser context can be closed without touching sibling runs.
        """


__all__ = ["IPromptAggregate", "IPromptFlowAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IPromptAggregate": IPromptAggregate,
    "IPromptFlowAggregate": IPromptFlowAggregate,
}
