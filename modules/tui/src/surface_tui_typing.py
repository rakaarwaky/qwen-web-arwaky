"""Surface: TUI shared mixin attribute protocol (AES surface naming).

Declares the app-state seams the Textual mixins read so they are not
untyped ``Any`` stubs (ARCH-1-003). Runtime objects still come from
``QwenTuiApp``; this Protocol is the typing surface only.
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
    from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
    from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
    from modules.shared.src.session.contract_session_protocol import (
        ISessionManagerProtocol,
        ISessionRotatorProtocol,
    )


@runtime_checkable
class QwenTuiAppLike(Protocol):
    """Attributes and seams the TUI mixins expect on the concrete app."""

    _NUM_SLOTS: int
    _slot_workers: MutableMapping[int, Any]
    _slot_cancel_events: MutableMapping[int, Any]
    _active_slot: int
    _sessions_loaded_once: bool
    _headless: bool
    session_manager: ISessionManagerProtocol | None
    agent_session_orchestrator: ISessionAggregate | None
    _session: ISessionAggregate
    _session_rotator: ISessionRotatorProtocol
    _prompt: IPromptAggregate
    _observability: IObservabilityProtocol
    _log_msg: Callable[..., None]


__all__ = ["QwenTuiAppLike"]
