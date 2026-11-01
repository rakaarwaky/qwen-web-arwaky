# BACKLOG — Prompt Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-25

## Progress Overview

The prompt feature is Done. `uv run python -m pytest modules/prompt/tests/ -m "not benchmark and not e2e" -q` green on 2026-10-24 (PROMPT-01 dispatch retry budget coordinated with CONFIG-02). No row is in progress or blocked; every backlog entry is Done.

## Backlog Status

### FR-PROMPT-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (2026-10-25, commit `d0ba69e`). The orchestrator routes the `direct` verb and builds the per-verb adapter. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). The orchestrator routes the `file` verb and builds the per-verb adapter. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). The orchestrator routes the `attachment` verb and builds the per-verb adapter. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_agent_cancel_terminal.py -v` → 14 passed (2026-10-25, commit `2152c8a`). The orchestrator routes the `cancel` verb. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_agent_cancel_terminal.py -v` → 14 passed (commit `2152c8a`). Targeted run cancellation signals one in-flight run without affecting others via `RunCancelRegistry`. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). The shared inject → send → wait flow applies the retry budget across verbs. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). `IInjectionProtocol` injects prompt text into the chat input through `PromptInjector`. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-008

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (2026-10-25, commit `2152c8a`). `ISendProtocol` triggers the send action through `SendDispatcher`. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-009

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). `ISaverProtocol` saves the response to the operator's destination through `Saver`. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-010

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py modules/prompt/tests/unit_agent_shared_flow_retry.py modules/prompt/tests/unit_prompt_dispatch_retry_budget.py -v` → 25 passed (commit `d0ba69e`). `IUploadProtocol` validates and uploads an attachment through `FileUploader`. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-011

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (2026-10-25, commit `2152c8a`). `capabilities_folder_compiler` compiles a folder to a single markdown file. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-PROMPT-012

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/prompt/tests/unit_transcript_selector_regression.py -v` → 14 passed (commit `2152c8a`). `capabilities_folder_compiler` resolves a folder to an attachment-ready file. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](../../PRD.md) |
| FRD | Feature requirements | [FRD.md](FRD.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
