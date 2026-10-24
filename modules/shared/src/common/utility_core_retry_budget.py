"""Utility layer (utility_core_retry_budget): resolve the dispatch retry budget.

Stateless resolver owned by CONFIG-02 and consumed by the prompt feature's
PROMPT-01: how many extra dispatch attempts the shared-flow dispatcher may
grant after the event-driven stall detector (``stall_timeout_sec``) cuts a
stream. The wall-clock response ceiling (CONFIG-02's ``timeout_sec``) stays
absolute and terminal per attempt; only the stall detector is retriable, and
only up to this budget. 0 keeps a stall terminal for the run — the default
pinned by ``unit_agent_shared_flow_retry.py`` and
``unit_transcript_selector_regression.py``.
"""

from __future__ import annotations

import os

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_DISPATCH_RETRY_BUDGET,
    DISPATCH_RETRY_BUDGET_ENV,
)
from modules.shared.src.common.taxonomy_core_vo import DispatchRetryBudget


def resolve_dispatch_retry_budget(
    override: int | DispatchRetryBudget | None = None,
) -> DispatchRetryBudget:
    """Resolve the stall-retry budget from the env override or the default.

    Precedence: an explicit non-negative ``override`` → the
    ``QWEN_DISPATCH_RETRY_BUDGET`` env var → ``DEFAULT_DISPATCH_RETRY_BUDGET``.
    Unparseable or negative env values fall back to the default so a
    malformed override cannot unbound the dispatch loop.
    """
    if override is not None:
        value = int(override)
        return DispatchRetryBudget(value) if value >= 0 else DispatchRetryBudget(0)
    raw = os.environ.get(DISPATCH_RETRY_BUDGET_ENV, "").strip()
    if not raw:
        return DispatchRetryBudget(DEFAULT_DISPATCH_RETRY_BUDGET)
    parsed = int(raw) if raw.isdigit() else -1
    return DispatchRetryBudget(parsed if parsed >= 0 else DEFAULT_DISPATCH_RETRY_BUDGET)
