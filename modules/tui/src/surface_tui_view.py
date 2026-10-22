"""Surface: TUI shared mixin attribute protocol (AES surface naming).

Declares the app-state seams the Textual mixins read so they are not
untyped ``Any`` stubs (ARCH-1-003). Runtime objects still come from
``QwenTuiApp``; this Protocol is the typing surface only.

Only taxonomy/utility types are referenced here — surface code may not
import contract(protocol).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class QwenTuiAppLike(Protocol):
    """Attributes and seams the TUI mixins expect on the concrete app."""

    _NUM_SLOTS: int
    _slot_workers: dict[int, Any]
    _slot_cancel_events: dict[int, Any]
    _active_slot_cache: int
    _sessions_loaded_once: bool
    _headless: bool
    _session_manager: Any
    _session: Any
    _session_rotator: Any
    _prompt: Any
    _log_msg: Callable[..., None]


__all__ = ["QwenTuiAppLike"]
