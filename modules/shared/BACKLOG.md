# BACKLOG — Shared Kernel

FRD: [DATA.md](DATA.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Progress Overview

- Done: `uv run python -m pytest modules/shared/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- Done: SHARED-01 acceptance scenario (session restore byte-identity) added to `unit_utility_session_backup.py`, 2026-10-24.
- In Progress: None.
- Next Action: `SHARED-02`, pin DOM query helpers against one captured chat transcript.

## Backlog Status

### DT-SHARED-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | — |
| Updated | 2026-10-24 |

### DT-SHARED-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-008

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-009

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-010

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-011

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P1 |
| Dependencies | None |
| Evidence | Pinned DOM query helpers in `unit_transcript_selector_regression.py` against captured transcript fixture (2026-10-25). `uv run python -m pytest modules/shared/tests/unit_transcript_selector_regression.py -v` → 19 passed (commit `4d7e5f3`). |
| Updated | 2026-10-25 |

### DT-SHARED-012

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `CONFIG-02` |
| Evidence | Documented the rate-limiter window semantics in `DATA.md` once the shared-flow retry budget settled. `uv run python -m pytest modules/shared/tests/ -q` → passes (2026-10-25, commit 2355b5d). |
| Updated | 2026-10-25 |

### DT-SHARED-013

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `CONFIG-02` |
| Evidence | Documented the rate-limiter window semantics in `DATA.md` once the shared-flow retry budget settled. `uv run python -m pytest modules/shared/tests/ -q` → passes (2026-10-25, commit 2355b5d). |
| Updated | 2026-10-25 |

### DT-SHARED-014

| Aspect | Detail |
| --- | --- |
| State | Done |
| Priority | P2 |
| Dependencies | `CONFIG-02` |
| Evidence | Documented the rate-limiter window semantics in `DATA.md` once the shared-flow retry budget settled. `uv run python -m pytest modules/shared/tests/ -q` → passes (2026-10-25, commit 2355b5d). |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| DATA.md | Data contract | [DATA.md](DATA.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
