# ROADMAP — qwen-web-arwaky

State / Health: **In Review / At Risk**. Last Updated: **2026-09-24**.

## Current Condition

- Done: `gh release view v6.4.0` reports a published release; source evidence is baseline commit `d8a9b60`.
- In Progress: None. In Review: `WS-01` documentation governance and `WS-02` benchmark and test layout convergence.
- Blocked: None. Manual authenticated-browser work is tracked as QA, not silently treated as done.
- Next: `WS-01`, `WS-02`, `WS-03`, `WS-04`.

## State Definitions

| State | Meaning |
|---|---|
| Idea | Not examined; no spec. |
| Refinement | Being specced. |
| Ready | Specified; not started. |
| In Progress | Active now. |
| Blocked | Name the blocker in Actual Condition. |
| In Review | PR open. |
| QA | Awaiting verification pass. |
| Done | Command + commit evidence. |
| Released | Shipped. |
| Deferred | Out of scope; reason in Actual Condition. |

| Health | Meaning |
|---|---|
| On Track | No threat to the gate. |
| At Risk | Gaps may miss the gate. |
| Blocked | Cannot proceed. |
| Ready for QA | Open rows clear; sweep left. |
| Ready for Release | Evidence recorded. |
| Released | Shipped. |

## Status Policy

- Verified, not self-reported: re-run the relevant command on the represented commit and cite the command, result, and commit hash (not “today”).
- The same PR updates every roadmap or backlog row invalidated by its changes.
- Root rows are cross-feature or infrastructure work only. Feature-specific work remains in that feature's `BACKLOG.md`.
- `Actual Condition` states what is true now, including blockers, failed checks, and the evidence still missing.
- `Done` requires passing verification evidence and a commit. `Released` additionally requires a published release or equivalent deployment evidence.
- `Owner` is a person or accountable team; `—` means unassigned and must not be interpreted as shared ownership.
- Priorities are `P0` (release or safety gate), `P1` (current milestone), and `P2` (follow-up).
- Prefixes: workspace `WS-` · CLI feature `CLI-` · Core feature `CORE-` · MCP feature `MCP-`. Feature rows stay in their own backlogs.
- New feature directories require both `FRD.md` and `BACKLOG.md`, plus a Feature Roll-up row in this file, in the same PR.
- Dates are ISO `YYYY-MM-DD`. `Updated` changes only when the row's condition, evidence, owner, state, or health changes.

## Release Readiness

### Phase Plan

Dates are target windows, not evidence that work shipped.

| Phase | Target window | Exit gate | Rows | State | Health |
|---|---|---|---|---|---|
| v6.4 baseline | 2026-09-21 | GitHub release is published and source baseline is identifiable. | — | Released | Released |
| Documentation governance baseline | 2026-09-24–2026-09-25 | Root roadmap exists; every feature has an FRD/backlog pair and is indexed. | `WS-01` | In Review | On Track |
| Backlog and infrastructure convergence | 2026-09-26–2026-10-02 | Duplicate benchmark work is resolved; open findings are revalidated and assigned or deferred with reasons. | `WS-02`, `WS-04` | Ready | At Risk |
| Reliability qualification | 2026-10-03–2026-10-09 | Single-attachment and 10-role swarm paths pass authenticated headed QA without aggressive resend or bot-verification loops. | `WS-03`, `CORE-01` | Ready | At Risk |
| Next release candidate | 2026-10-10–2026-10-16 | P0 rows are clear, automated gates pass on one commit, manual evidence is recorded, and feature roll-ups are Ready for Release. | `WS-03`, feature backlogs | Refinement | At Risk |

### Branches in Flight

This table tracks branches with current roadmap relevance; the existence of an old remote branch alone does not make it active.

| Branch | Backlog IDs | State |
|---|---|---|
| `arena/01a0d304-qwen-web-arwaky` | `WS-01` | In Review / PR #432 |
| `refactor/benchmark-structure` | `WS-02` | In Review / PR #428 |
| `feat/benchmark-suite` | `WS-02` | In Review / PR #426; overlap must be resolved |

## Backlog

Only work spanning multiple features or repository infrastructure belongs here.

| ID | Item | Priority | State | Health | Owner | Target | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|---|
| WS-01 | Establish roadmap and paired feature backlogs | P0 | In Review | On Track | — | 2026-09-25 | Commit `4d4e2c0` adds the root roadmap and three paired feature backlogs; the documentation contract check passed, and PR [#432](https://github.com/rakaarwaky/qwen-web-arwaky/pull/432) is open. Drift finding #386 remains in the revalidation scope. | Address review, rerun the documentation contract check on the final commit, and record merge evidence. | 2026-09-24 |
| WS-02 | Converge benchmark and test layout | P1 | In Review | At Risk | — | 2026-10-02 | PR [#428](https://github.com/rakaarwaky/qwen-web-arwaky/pull/428) at `fb13aa9` passes tests/self-lint but fails lint/mypy; overlapping PR [#426](https://github.com/rakaarwaky/qwen-web-arwaky/pull/426) remains open after #427 merged. | Select the surviving layout, fix its required checks, and close superseded work. | 2026-09-24 |
| WS-03 | Qualify attachment, swarm, and release reliability end to end | P0 | QA | At Risk | — | 2026-10-09 | Patient-send fixes from PRs #423/#424 are in the `d8a9b60` baseline, but the authenticated manual scenarios in [`ISSUE.md`](ISSUE.md) remain unchecked and stakeholder walkthrough finding #321 remains open. | Re-run one attachment and a 10-role headed swarm; record command, commit, outcomes, and challenge behavior. | 2026-09-24 |
| WS-04 | Revalidate cross-cutting security, quality, operations, and release findings | P0 | Refinement | At Risk | — | 2026-10-02 | Open findings include runbooks/incident response (#299, #355), test and quality governance (#329, #340), release strategy (#325), and packaging/dependency claims (#289, #349). Some claims predate `uv.lock` and recent fixes, so issue state alone is not proof of current behavior. | Reproduce each finding on `d8a9b60`; close stale reports and route confirmed work to one owning row. | 2026-09-24 |

## Feature Roll-up

Every feature directory is indexed here; implementation detail remains in its backlog. Per [`ARCHITECTURE.md`](ARCHITECTURE.md), `modules/shared` is the cross-feature contract/taxonomy member and its `modules/shared/templates` role-template package data, so neither is a feature directory.

| ID | Item | Priority | Spec | Backlog | State | Health | Owner | Next | Updated |
|---|---|---|---|---|---|---|---|---|---|
| `modules/prompt` | Prompt execution and attachment | P0 | [FRD](modules/prompt/FRD.md) | [BACKLOG](modules/prompt/BACKLOG.md) | QA | At Risk | — | `PROMPT-01` | 2026-09-24 |
| `modules/session` | Session pool and rotation | P0 | [FRD](modules/session/FRD.md) | [BACKLOG](modules/session/BACKLOG.md) | In Review | On Track | — | `SESSION-02` | 2026-10-18 |
| `modules/jobs` | Async job and folder compilation | P1 | [FRD](modules/jobs/FRD.md) | [BACKLOG](modules/jobs/BACKLOG.md) | Refinement | At Risk | — | `JOB-01` | 2026-09-24 |
| `modules/swarm` | Swarm execution | P1 | [FRD](modules/swarm/FRD.md) | [BACKLOG](modules/swarm/BACKLOG.md) | Refinement | At Risk | — | `SWARM-01` | 2026-09-24 |
| `modules/logging` | Observability and metrics | P1 | [FRD](modules/logging/FRD.md) | [BACKLOG](modules/logging/BACKLOG.md) | Refinement | At Risk | — | `LOG-01` | 2026-09-24 |
| `modules/browser` | Browser adapter | P0 | [FRD](modules/browser/FRD.md) | [BACKLOG](modules/browser/BACKLOG.md) | Refinement | At Risk | — | `BROWSER-01` | 2026-09-24 |
| `modules/config` | Configuration | P1 | [FRD](modules/config/FRD.md) | [BACKLOG](modules/config/BACKLOG.md) | Refinement | On Track | — | `CFG-01` | 2026-09-24 |
| `modules/update` | Product update | P2 | [FRD](modules/update/FRD.md) | [BACKLOG](modules/update/BACKLOG.md) | Deferred | At Risk | — | `UPDATE-01` | 2026-09-24 |
| `modules/cli` | CLI and Textual TUI | P1 | [DESIGN](modules/cli/DESIGN.md) | [BACKLOG](modules/cli/BACKLOG.md) | Refinement | At Risk | — | `CLI-01` | 2026-09-24 |
| `modules/tui` | Textual TUI | P1 | [DESIGN](modules/tui/DESIGN.md) | [BACKLOG](modules/tui/BACKLOG.md) | Refinement | At Risk | — | `TUI-01` | 2026-09-24 |
| `modules/mcp` | MCP Server Surface | P1 | [DESIGN](modules/mcp/DESIGN.md) | [BACKLOG](modules/mcp/BACKLOG.md) | Refinement | At Risk | — | `MCP-01` | 2026-09-24 |

Note: `modules/core` was removed during the AES module split. Its feature rows are now owned by `modules/prompt` and `modules/session`; the legacy `CORE-*` identifiers in the risk register map to `PROMPT-*` and `SESSION-*` respectively.

## Risk Register

- Risk: roadmap state drifts from feature detail and engineers act on stale status. Mitigation: `WS-01`.
- Risk: competing benchmark branches merge incompatible repository layouts or leave CI red. Mitigation: `WS-02`.
- Risk: attachment parsing or resend behavior triggers `SendDispatchError` or anti-bot verification in a release. Mitigation: `WS-03`, `PROMPT-01`.
- Risk: unresolved security and operations reports ship without current reproduction or explicit acceptance. Mitigation: `WS-04`, `PROMPT-05`, `PROMPT-06`, `MCP-02`.
- Risk: Qwen UI or model changes invalidate selectors, completion detection, or hardcoded model verification. Mitigation: `PROMPT-01`, `PROMPT-03`.
- Risk: async job and swarm concurrency leak resources or stall callers. Mitigation: `PROMPT-02`, `MCP-01`.
