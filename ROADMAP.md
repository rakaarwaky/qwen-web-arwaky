# ROADMAP — qwen-web-arwaky

Last Updated: 2026-10-25

## Progress Overview

The core prompt, session, jobs, browser, config, logging, CLI, MCP, and update modules are all at Done. Swarm execution and the TUI release-evidence trail remain open; both are tracked in the Roadmap Status below. State vocabulary: **Ready** (specified, not started; blockers named), **In Progress** (active now), **In Review** (PR open, awaiting verification), **Done** (command + commit evidence; shipped releases carry release evidence).

## Roadmap Status

Feature detail stays in each feature's `BACKLOG.md`; per [`ARCHITECTURE.md`](ARCHITECTURE.md), `modules/shared` is the cross-feature contract/taxonomy member and its `modules/shared/templates` role-template package data, so neither is a feature directory. Entries are priority-ordered: all P0 first, then P1, then P2; the NNN counter is global and sequential.

### PR-QWA-001: Direct prompt execution — browser

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-002: Prompt-file execution — cli

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-003: Prompt with document execution — config

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-004: Authenticated session handling — jobs

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | `SESSION-03`                                                                                             |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/session/FRD.md)                                                                            |
| Backlog      | [BACKLOG](modules/session/BACKLOG.md)                                                                    |

### PR-QWA-005: Isolated conversation context — logging

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-006: Complete response detection — mcp

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-007: Durable local results — prompt

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/prompt/FRD.md)                                                                             |
| Backlog      | [BACKLOG](modules/prompt/BACKLOG.md)                                                                     |

### PR-QWA-008: Safe local path boundaries — prompt_runtime

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P0                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/session/FRD.md)                                                                            |
| Backlog      | [BACKLOG](modules/session/BACKLOG.md)                                                                    |

### PR-QWA-009: Asynchronous job control — session

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | `JOBS-01`                                                                                                 |
| Updated      | 2026-10-24                                                                                                |
| Spec         | [FRD](modules/jobs/FRD.md)                                                                                |
| Backlog      | [BACKLOG](modules/jobs/BACKLOG.md)                                                                        |

### PR-QWA-010: Concurrent-run isolation — swarm

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Ready                                                                                                     |
| Next Action  | `SWARM-01`                                                                                              |
| Updated      | 2026-09-24                                                                                                |
| Spec         | [FRD](modules/swarm/FRD.md)                                                                               |
| Backlog      | [BACKLOG](modules/swarm/BACKLOG.md)                                                                      |

### PR-QWA-011: Folder prompt preparation — tui

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [FRD](modules/jobs/FRD.md)                                                                                |
| Backlog      | [BACKLOG](modules/jobs/BACKLOG.md)                                                                        |

### PR-QWA-012: Workspace readiness diagnostics — update

| Aspect       | Detail                                                                                                    |
|--------------|----------------------------------------------------------------------------------------------------------|
| Priority     | P1                                                                                                        |
| State        | Done                                                                                                      |
| Next Action  | None                                                                                                      |
| Updated      | 2026-10-25                                                                                                |
| Spec         | [DESIGN](modules/cli/DESIGN.md)                                                                           |
| Backlog      | [BACKLOG](modules/cli/BACKLOG.md)                                                                        |


---


## Reference

- PRD: [PRD.md](PRD.md)
- ROADMAP: [ROADMAP.md](ROADMAP.md)
- ARCHITECTURE: [ARCHITECTURE.md](ARCHITECTURE.md)
