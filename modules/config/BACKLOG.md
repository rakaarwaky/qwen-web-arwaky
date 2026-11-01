# BACKLOG — Config Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Progress Overview

- Done: `uv run python -m pytest modules/config/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; CONFIG-03 pinned on 2026-10-24.
- In Progress: None.
- Blocked: None.
- Next Action: `CONFIG-01`, the multi-fault finding acceptance gap.

## Backlog Status

### FR-CONFIG-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | `PROMPT-01` |
| Evidence | `timeout_sec` is the absolute per-attempt response ceiling (FR-PROMPT-006), pinned with PROMPT-01 on 2026-10-22. `uv run python -m pytest modules/config/tests/unit_agent_config_orchestrator.py -v` → 10 passed (2026-10-25, commit 75748ff). |
| Updated | 2026-10-25 |

### FR-CONFIG-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Add an acceptance scenario proving a config with several invalid fields reports every one in one call. `uv run python -m pytest modules/config/tests/acceptance_config_finding_completeness.py -v` → 2 passed (2026-10-25, commit 00124e4). |
| Updated | 2026-10-25 |

### FR-CONFIG-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | None |
| Evidence | Capacity ceiling returns the single-worker default when the host reports no usable memory (FR-CONFIG-004), pinned in `unit_capability_config_inspection.py`. `uv run python -m pytest modules/config/tests/unit_capability_config_inspection.py -v` → 22 passed (2026-10-25, commit 68eb0fb). |
| Updated | 2026-10-25 |

### FR-CONFIG-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | None |
| Evidence | Host capacity is reported through the inspection seam, including the single-worker fallback on a host with no usable memory. `uv run python -m pytest modules/config/tests/unit_capability_config_inspection.py -v` → 22 passed (2026-10-25, commit 68eb0fb). |
| Updated | 2026-10-25 |

### FR-CONFIG-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | None |
| Evidence | A slot's widget values are resolved into a run plan the orchestrator reads. `uv run python -m pytest modules/config/tests/ -v` (config suite green at `refactor/aes-zero-violations`). |
| Updated | 2026-10-25 |

### FR-CONFIG-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | None |
| Evidence | The run workspace is initialized before a run starts; a not-yet-existing output directory is accepted. `uv run python -m pytest modules/config/tests/unit_capability_config_inspection.py -v` → 22 passed (2026-10-25, commit 68eb0fb). |
| Updated | 2026-10-25 |

### FR-CONFIG-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | None |
| Evidence | Host health is probed for the update smoke gate. `uv run python -m pytest modules/config/tests/ -v` (config suite green at `refactor/aes-zero-violations`). |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| FRD.md | Feature requirements | [FRD.md](FRD.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
