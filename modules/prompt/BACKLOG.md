# BACKLOG — Prompt Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/prompt/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `PROMPT-01`, the stall-ceiling interaction gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| PROMPT-01 | P1 | Ready | At Risk | `CONFIG-02` | Specify the retry budget that feeds the shared rate limiter and pin the stall-ceiling interaction. | 2026-10-05 |
| PROMPT-02 | P1 | Ready | On Track | None | Add an acceptance scenario proving a cancel on a pipeline that reached a terminal state reports zero. | 2026-10-05 |
| PROMPT-03 | P2 | Ready | On Track | `SHARED-02` | Pin the stream-monitor DOM selectors against one captured transcript so drift fails the prompt suite. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A direct prompt produces a response file at the named destination | Automated | `modules/prompt/tests/unit_agent_direct_prompt.py` | direct prompt save | 2026-10-05 |
| A stalled stream reports incomplete | Automated | `modules/prompt/tests/unit_capability_stream_monitor.py` | stall detection | 2026-10-05 |
| An attachment over the upload limit is rejected | Automated | `modules/prompt/tests/unit_capability_file_uploader.py` | upload limit | 2026-10-05 |
| A cancel on a terminal pipeline reports zero | Gap | none yet | see `PROMPT-02` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `CONFIG-02` owns the response ceiling this feature's stall detector coordinates with.
- `SHARED-02` owns the pinned DOM helpers the stream monitor reads.
- `JOBS-01` owns the backpressure this feature's job submissions encounter.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/prompt/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `PROMPT-02`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Multi-attachment prompts stay out of scope; one attachment per request.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
