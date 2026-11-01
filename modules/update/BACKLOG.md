# BACKLOG — Update Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-25

## Progress Overview

The update feature is Done. `uv run python -m pytest modules/update/tests/ -v` → 35 passed (2026-10-25, commits `4c98863` and `fd55857`); `FR-UPDATE-001` through `FR-UPDATE-004` are all Done with version reporting, upgrade, postflight verification, and rollback-ordering evidence. No row is in progress or blocked.

## Backlog Status

### FR-UPDATE-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/update/tests/ -v` → 35 passed (2026-10-25, commit `4c98863`). The installed and latest versions are reported against the surface contract. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-UPDATE-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/update/tests/ -v` → 35 passed (2026-10-25, commits `4c98863` and `fd55857`). The package upgrades and the browser syncs under the managed-build trust rule; six cross-cutting findings (#299, #355, #329, #340, #325, #289/#349) revalidated against the current contract. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-UPDATE-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/update/tests/acceptance_update_postflight_rollback.py -v` → 2 passed (2026-10-25, commit `fd55857`). A postflight failure routes through the same rollback path a health-gate failure uses. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-UPDATE-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/update/tests/acceptance_update_rollback_ordering.py modules/update/tests/unit_update_manager_rollback.py -v` → passes (2026-10-25, commit `fa89616`). Rollback ordering is pinned: a failed health gate restores the install before the browser build. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals and scope | [PRD.md](../../PRD.md) |
| FRD | Functional requirements specification | [FRD.md](FRD.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
