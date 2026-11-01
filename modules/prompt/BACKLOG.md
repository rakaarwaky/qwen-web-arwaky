# BACKLOG — Prompt Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Progress Overview

- Done: `uv run python -m pytest modules/prompt/tests/ -m "not benchmark and not e2e" -q` green on 2026-10-24 (PROMPT-01 dispatch retry budget coordinated with CONFIG-02).
- In Progress: None.
- Blocked: None.
- Next Action: None — every backlog row is Done.

## Backlog Status

### FR-PROMPT-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_agent_cancel_terminal.py -v` → 14 passed (2026-10-25, commit 2152c8a). |
| Updated | 2026-10-22 |

### FR-PROMPT-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_agent_cancel_terminal.py -v` → 14 passed (2026-10-25, commit 2152c8a). |
| Updated | 2026-10-22 |

### FR-PROMPT-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-008

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `SHARED-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (2026-10-25, commit 2152c8a). |
| Updated | 2026-10-22 |

### FR-PROMPT-009

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-010

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `CONFIG-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit d0ba69e). |
| Updated | 2026-10-25 |

### FR-PROMPT-011

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `SHARED-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (2026-10-25, commit 2152c8a). |
| Updated | 2026-10-22 |

### FR-PROMPT-012

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `SHARED-02` |
| Evidence | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (2026-10-25, commit 2152c8a). |
| Updated | 2026-10-22 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| FRD.md | Feature requirements | [FRD.md](FRD.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
