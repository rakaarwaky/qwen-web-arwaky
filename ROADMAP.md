# ROADMAP — qwen-web-arwaky

Last Updated: 2026-10-25

## Progress Overview

The core prompt, session, jobs, browser, config, logging, CLI, MCP, and update modules are all at Done. Swarm execution and the TUI release-evidence trail remain open; both are tracked in the Roadmap Status below. State vocabulary: **Ready** (specified, not started; blockers named), **In Progress** (active now), **In Review** (PR open, awaiting verification), **Done** (command + commit evidence; shipped releases carry release evidence).

## Roadmap Status

Feature detail stays in each feature's `BACKLOG.md`; per [`ARCHITECTURE.md`](ARCHITECTURE.md), `modules/shared` is the cross-feature contract/taxonomy member and its `modules/shared/templates` role-template package data, so neither is a feature directory. Entries are priority-ordered: all P0 first, then P1, then P2; the NNN counter is global and sequential.

### PR-QWA-001: Direct prompt execution

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-002: Prompt-file execution

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-003: Prompt with document execution

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-004: Authenticated session handling

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | `SESSION-03`                                                                                             |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/session/FRD.md)                                                                            |
| Backlog      | [BACKLOG](modules/session/BACKLOG.md)                                                                    |

### PR-QWA-005: Isolated conversation context

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-006: Complete response detection

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-007: Durable local results

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-008: Safe local path boundaries

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/session/FRD.md)                                                                            |
| Backlog      | [BACKLOG](modules/session/BACKLOG.md)                                                                    |

### PR-QWA-009: Asynchronous job control

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | `JOBS-01`                                                                                                 |
| Updated      | 2026-10-24                                                                                                |
| Spec         | [FRD](modules/jobs/FRD.md)                                                                                |
| Backlog      | [BACKLOG](modules/jobs/BACKLOG.md)                                                                        |

### PR-QWA-010: Concurrent-run isolation

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Ready                                                                                                     |
| Next Action  | `SWARM-01`                                                                                              |
| Updated      | 2026-09-24                                                                                                |
| Spec         | [FRD](modules/swarm/FRD.md)                                                                               |
| Backlog      | [BACKLOG](modules/swarm/BACKLOG.md)                                                                      |

### PR-QWA-011: Folder prompt preparation

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/jobs/FRD.md)                                                                                |
| Backlog      | [BACKLOG](modules/jobs/BACKLOG.md)                                                                        |

### PR-QWA-012: Workspace readiness diagnostics

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [DESIGN](modules/cli/DESIGN.md)                                                                           |
| Backlog      | [BACKLOG](modules/cli/BACKLOG.md)                                                                        |

### PR-QWA-013: Interactive terminal operation

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | In Progress                                                                                               |
| Next Action  | `TUI-01` release-evidence recording (tracked in #721)                                                    |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [DESIGN](modules/tui/DESIGN.md)                                                                          |
| Backlog      | [BACKLOG](modules/tui/BACKLOG.md)                                                                        |

### PR-QWA-014: Optional external observability

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P2                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/logging/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/logging/BACKLOG.md)                                                                    |

### PR-QWA-015: Guided product updates

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P2                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/update/FRD.md)                                                                              |
| Backlog      | [BACKLOG](modules/update/BACKLOG.md)                                                                     |

### PR-QWA-016: Machine-readable diagnostics

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P2                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [DESIGN](modules/mcp/DESIGN.md)                                                                          |
| Backlog      | [BACKLOG](modules/mcp/BACKLOG.md)                                                                        |

### Workspace Condition and Risks

- **In Progress**: `modules/tui` TUI-01 release-evidence recording (tracked in #721).
- **Done**: `modules/prompt`, `modules/session`, `modules/jobs`, `modules/logging`, `modules/browser`, `modules/config`, `modules/update`, `modules/mcp`, and `modules/cli` roll-ups advanced to Done on 2026-10-25.
- **Blocked**: None. **Next**: None.

Cross-cutting risks:

- Risk: attachment parsing or resend behavior triggers `SendDispatchError` or anti-bot verification in a release. Mitigation: `PROMPT-01`.
- Risk: unresolved security and quality reports ship without current reproduction or explicit acceptance. Mitigation: `PROMPT-05`, `PROMPT-06`, `MCP-02`.
- Risk: Qwen UI or model changes invalidate selectors, completion detection, or hardcoded model verification. Mitigation: `PROMPT-01`, `PROMPT-03`.
- Risk: async job and swarm concurrency leak resources or stall callers. Mitigation: `PROMPT-02`, `MCP-01`.

## Reference

| Artifact | Purpose | Link |
|----------|---------|------|
| PRD | Product scope, requirements, and success metrics | [PRD.md](PRD.md) |
| ARCHITECTURE | Layer boundaries and allowed dependencies | [ARCHITECTURE.md](ARCHITECTURE.md) |
