"""Utility layer: per-run target-model contextvar for the browser model picker.

Issue #283: the targeted model is per-run configuration. A contextvars token
lets concurrent runs (Swarm fan-out, parallel jobs) keep their own override
without mutating shared state. The override is active only for runs that
received an AppConfig with a non-empty ``model`` field; the constant-level
default (QWEN_DEFAULT_MODEL / QWEN_MODEL env var) is preserved otherwise.

Stateless helpers only (utility layer); taxonomy imports. The token lives
here — the shared utility layer — so both the model-policy capability and the
browser adapter that binds it read/write the same object without a
capability-to-capability import.
"""

from __future__ import annotations

import contextvars

from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL
from modules.shared.src.common.taxonomy_core_vo import ModelLabel

# The token lives in the shared utility layer so both the capability and the
# browser adapter read/write the same object.
_TARGET_MODEL: contextvars.ContextVar[str] = contextvars.ContextVar("qwa_target_model", default=DEFAULT_MODEL)


def bind_target_model(target: ModelLabel) -> None:
    """Bind *target* into the per-run model contextvar."""
    _TARGET_MODEL.set(target)


def target_model() -> ModelLabel:
    """Return the model a running pipeline should target.

    ``ContextVar.get()`` returns the raw stored value, which in tests may be
    a ``MagicMock`` (leaked by a prior unmocked ``browser_session`` call).
    Only a genuine string is a valid target; anything else falls back to
    the default.
    """
    value = _TARGET_MODEL.get()
    if isinstance(value, str) and value:
        return ModelLabel(value)
    return ModelLabel(DEFAULT_MODEL)


__all__ = ["bind_target_model", "target_model"]
