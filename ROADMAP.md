# ROADMAP — qwen-web-arwaky

State: vocabulary below. Last Updated: 2026-10-24.

## Current Condition

- In Progress: `modules/tui` TUI-01 release-evidence recording (tracked in #721).
- Done: `modules/prompt`, `modules/session`, `modules/jobs`, `modules/logging`, `modules/browser`, `modules/config`, `modules/update`, `modules/mcp`, and `modules/cli` roll-ups advanced to Done on 2026-10-25.
- Blocked: None
- Next: None

## State Definitions

| State | Meaning |
|---|---|
| Ready | Specified; not started. Blockers, if any, are named in Actual Condition. |
| In Progress | Active now. |
| In Review | PR open; awaiting verification pass. |
| Done | Command + commit evidence; shipped releases carry release evidence. |

## Feature Roll-up

One table: every feature row. Feature detail stays in each feature's `BACKLOG.md`; per [`ARCHITECTURE.md`](ARCHITECTURE.md), `modules/shared` is the cross-feature contract/taxonomy member and its `modules/shared/templates` role-template package data, so neither is a feature directory.

| ID | Feature | Priority | State | Dependencies | Next Action | Updated |
|---|---|---|---|---|---|---|
| `modules/prompt` | Prompt execution and attachment | P0 | Done | Spec: [FRD](modules/prompt/FRD.md) · Backlog: [BACKLOG](modules/prompt/BACKLOG.md) | None | 2026-10-25 |
| `modules/session` | Session pool and rotation | P0 | Done | Spec: [FRD](modules/session/FRD.md) · Backlog: [BACKLOG](modules/session/BACKLOG.md) | `SESSION-03` | 2026-10-25 |
| `modules/browser` | Browser adapter | P0 | Done | Spec: [FRD](modules/browser/FRD.md) · Backlog: [BACKLOG](modules/browser/BACKLOG.md) | None | 2026-10-25 |
| `modules/jobs` | Async job and folder compilation | P1 | Done | Spec: [FRD](modules/jobs/FRD.md) · Backlog: [BACKLOG](modules/jobs/BACKLOG.md) | `JOBS-01` | 2026-10-24 |
| `modules/swarm` | Swarm execution | P1 | Ready | Spec: [FRD](modules/swarm/FRD.md) · Backlog: [BACKLOG](modules/swarm/BACKLOG.md) | `SWARM-01` | 2026-09-24 |
| `modules/logging` | Observability and metrics | P1 | Done | Spec: [FRD](modules/logging/FRD.md) · Backlog: [BACKLOG](modules/logging/BACKLOG.md) | None | 2026-10-25 |
| `modules/config` | Configuration | P1 | Done | Spec: [FRD](modules/config/FRD.md) · Backlog: [BACKLOG](modules/config/BACKLOG.md) | None | 2026-10-25 |
| `modules/cli` | CLI and Textual TUI | P1 | Done | Spec: [DESIGN](modules/cli/DESIGN.md) · Backlog: [BACKLOG](modules/cli/BACKLOG.md) | None | 2026-10-25 |
| `modules/tui` | Textual TUI | P1 | Done | Spec: [DESIGN](modules/tui/DESIGN.md) · Backlog: [BACKLOG](modules/tui/BACKLOG.md) | `TUI-01` | 2026-10-25 |
| `modules/mcp` | MCP Server Surface | P1 | Done | Spec: [DESIGN](modules/mcp/DESIGN.md) · Backlog: [BACKLOG](modules/mcp/BACKLOG.md) | None | 2026-10-25 |
| `modules/update` | Product update | P2 | Done | Spec: [FRD](modules/update/FRD.md) · Backlog: [BACKLOG](modules/update/BACKLOG.md) | None | 2026-10-25 |

## Risk Register

- Risk: attachment parsing or resend behavior triggers `SendDispatchError` or anti-bot verification in a release. Mitigation: `PROMPT-01`.
- Risk: unresolved security and quality reports ship without current reproduction or explicit acceptance. Mitigation: `PROMPT-05`, `PROMPT-06`, `MCP-02`.
- Risk: Qwen UI or model changes invalidate selectors, completion detection, or hardcoded model verification. Mitigation: `PROMPT-01`, `PROMPT-03`.
- Risk: async job and swarm concurrency leak resources or stall callers. Mitigation: `PROMPT-02`, `MCP-01`.
