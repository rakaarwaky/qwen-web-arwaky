"""Capabilities: cancel a running Swarm fan-out (AES403).

Implements ISwarmCancelProtocol.

One file per protocol seam. This file owns ``ISwarmCancelProtocol`` — the
single method that stops every leg of a running fan-out, marks the
survivors cancelled, and shuts the executor down.

The cancel events, the attachment handle, and the executor all live in the
shared registry this seam is handed, the same registry the start and
progress seams use; no seam imports another, so a cancel always reaches
the run the caller is looking at.
"""

from __future__ import annotations

import logging

from modules.shared.src.common.taxonomy_core_vo import CancelToken
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest
from modules.shared.src.swarm.contract_swarm_protocol import (
    ISwarmCancelProtocol,
    ISwarmRegistryProtocol,
)
from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmId
from modules.shared.src.swarm.utility_swarm_runner_base import mark_cancelled

log = logging.getLogger(__name__)


# ─── Block 1: Class Definition & Constructor ────────────
class SwarmCancelRunner(ISwarmCancelProtocol):
    """Cancel a running fan-out on behalf of the swarm orchestrator.

    A cancel is best-effort and idempotent: an unknown swarm id, or one
    that already reached a terminal state, leaves the recorded outcome
    alone. Only the legs that had not finished are marked cancelled, so a
    cancel never rewrites work that actually completed.
    """

    def __init__(self, registry: ISwarmRegistryProtocol, attachment: IPromptAggregate) -> None:
        """Bind the cancel seam to the registry and the aggregate whose browsers must stop.

        Args:
            registry: The store holding the snapshots, cancel events, and
                executor of every run.
            attachment: The aggregate whose in-flight browser contexts are
                told to close, reached through its typed ``request_cancel``
                verb.
        """
        self._registry = registry
        self._attachment = attachment

    def cancel(self, swarm_id: SwarmId) -> None:
        """Stop active browser contexts and prevent queued work from running."""
        if self._registry.get_snapshot(swarm_id) is None:
            return
        events = self._registry.cancel_events(swarm_id)
        for event in events.values():
            event.set()
        for event in events.values():
            self._request_attachment_cancel(event)
        self._registry.revise(swarm_id, mark_cancelled)
        executor = self._registry.release(swarm_id)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def _request_attachment_cancel(self, event: CancelToken) -> None:
        """Forward a cancel event to the attachment aggregate via its typed seam.

        ``IPromptAggregate.request_cancel`` is a first-class contract
        operation, so the Swarm cancel seam reaches it through ``execute``
        with the ``request_cancel`` verb rather than duck-typing on an
        attribute that may or may not exist (issue #360). The response is
        discarded: a fan-out cancel is best-effort and reports at the
        fan-out level, so no caller consumes a per-leg count.
        """
        self._attachment.execute(PromptRequest(verb="request_cancel", cancel_event=event))


__all__ = ["SwarmCancelRunner"]
