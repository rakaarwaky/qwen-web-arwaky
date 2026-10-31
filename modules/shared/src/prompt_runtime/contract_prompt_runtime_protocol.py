"""Contract protocols for the prompt_runtime feature: six capability seams.

One trait per capability seam, one seam per FR-RUNTIME requirement:

- ``IRuntimeInjectProtocol`` (FR-RUNTIME-001) — inject prompt text
- ``IRuntimeSendProtocol`` (FR-RUNTIME-002) — dispatch the send action
- ``IRuntimeWatchProtocol`` (FR-RUNTIME-003) — watch the response stream
- ``IRuntimeUploadProtocol`` (FR-RUNTIME-004) — upload an attachment
- ``IRuntimePersistProtocol`` (FR-RUNTIME-005) — persist the artifact
- ``IRuntimeDoorProtocol`` (FR-RUNTIME-006) — the single routing door

The five capability seams extend the seam declarations the prompt feature
owns in the shared prompt contract, so a capability satisfied for both
features by one class: consumers keep depending on shared contracts,
never on this module's implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.prompt.contract_prompt_protocol import (
    IInjectionProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    IUploadProtocol,
)
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest, RuntimeResponse

__all__ = [
    "IRuntimeDoorProtocol",
    "IRuntimeInjectProtocol",
    "IRuntimePersistProtocol",
    "IRuntimeSendProtocol",
    "IRuntimeUploadProtocol",
    "IRuntimeWatchProtocol",
]

_layer_symbols = __all__


class IRuntimeInjectProtocol(IInjectionProtocol):
    """Seam FR-RUNTIME-001: locate the chat input and inject prompt text.

    Carries ``find_input`` and ``inject_text`` from the shared injection
    seam; a runtime capability satisfied here is satisfied for the prompt
    feature's pipeline too.
    """


class IRuntimeSendProtocol(ISendProtocol):
    """Seam FR-RUNTIME-002: dispatch the send action and report the turn.

    Carries ``click_send``, ``count_messages``, and
    ``latest_message_text`` from the shared send seam.
    """


class IRuntimeWatchProtocol(IStreamProtocol):
    """Seam FR-RUNTIME-003: follow the stream to a terminal verdict.

    Carries ``wait_for_response``, ``is_generation_complete``, and
    ``is_thinking_active`` from the shared stream seam.
    """


class IRuntimeUploadProtocol(IUploadProtocol):
    """Seam FR-RUNTIME-004: validate and attach a file to the chat.

    Carries ``upload_attachment`` and ``validate_file`` from the shared
    upload seam, including the pre-flight byte ceiling.
    """


class IRuntimePersistProtocol(ISaverProtocol):
    """Seam FR-RUNTIME-005: write the artifact and its sidecar.

    Carries ``write_output`` from the shared save seam: ``0o600``
    artifact, ``.meta.json`` under the metadata directory.
    """


class IRuntimeDoorProtocol(ABC):
    """Seam FR-RUNTIME-006: one door that routes any runtime verb.

    Adding a verb means extending the request VO, never adding a second
    entry point; an unknown verb is refused with the configuration
    defect named.
    """

    @abstractmethod
    def execute(self, request: RuntimeRequest) -> RuntimeResponse:
        """Route one runtime request to the capability serving its verb."""
