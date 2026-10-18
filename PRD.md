# PRD — qwen-web-arwaky

> Product Requirements Document. Describes WHAT this project does and WHY.
> Audience: Stakeholders, PM, Design, Engineering leads.
> Condition: [Prompt FRD](modules/prompt/FRD.md), [Session FRD](modules/session/FRD.md), [CLI DESIGN](modules/cli/DESIGN.md) + [CLI BACKLOG](modules/cli/BACKLOG.md), [MCP DESIGN](modules/mcp/DESIGN.md) + [MCP BACKLOG](modules/mcp/BACKLOG.md).
> This file is specification only.

## Problem Statement

Developers, local automation operators, and AI agents need to submit substantial prompts and documents to `chat.qwen.ai` without repeatedly operating the website by hand or depending on a paid API. Manual runs are slow to reproduce, difficult to audit, and vulnerable to lost output when authentication expires, the site changes, or a long response is interrupted. Without a reliable local product boundary, unattended workflows cannot determine whether work completed, where the result was saved, or what action is required after failure.

## Goals & Success Metrics

| # | Goal | Measurement | Target |
|---|------|-------------|--------|
| 1 | Complete prompt workflows reliably under controlled service availability | A 100-run acceptance exercise covering direct text, prompt files, and prompt-plus-document runs | At least 99 successful terminal outcomes out of 100 runs, with every failure reported explicitly |

**Goal 1 acceptance protocol:** Before a reliability claim is made for Goal 1, a QA-approved versioned sampling protocol must be on record that states: the supported account tier and region, service-health preconditions that must hold before sampling, the workflow allocation across the 100 runs, how many initial attempts are made, how retries are counted, which exclusions are valid and why, what makes a sample valid, and the QA approval signature. An unapproved protocol blocks the reliability claim. The existing 100-run / 99-success target remains in force.
| 2 | Preserve every accepted result and its audit trail | Compare terminally successful runs with readable result files and corresponding run records | 100% of successful runs have both artifacts |
| 3 | Give command-line and agent clients equivalent access to the primary prompt workflows | Cross-surface acceptance matrix for direct text, prompt files, and prompt-plus-document runs | 3 of 3 workflows produce the same success, failure, and result-location information on both surfaces |
| 4 | Keep asynchronous agent calls responsive during long generations | Measure elapsed time from accepted submission to receipt of a tracking identifier in 30 queued-run trials | p95 at or below 2 seconds |
| 5 | Prevent one failed parallel run from terminating unrelated work | Ten-run isolation exercise with one forced authentication or generation failure | All 9 unaffected runs reach their own terminal outcome |

## User Personas

- **Independent developer working without an API budget**: needs to send large local prompts and documents at no API cost, cannot supervise every browser interaction, and considers the job done when a complete response is stored at a known location with a traceable run record.
- **AI coding agent operating through a local tool connection**: needs predictable machine-readable acceptance, progress, success, and failure responses; it cannot solve interactive challenges or infer state from a visible browser.
- **Automation operator running unattended jobs overnight**: needs isolated runs, bounded waiting, and actionable diagnostics; they cannot inspect each open session and consider the system successful when every submitted job reaches an auditable terminal state.
- **Developer maintaining automation after an upstream website change**: needs failures to be explicit and reproducible rather than silently producing partial content; done means a regression can be demonstrated without risking user data.

## Scope

- **In scope**: local automation of authenticated `chat.qwen.ai` prompt workflows; direct-text, prompt-file, and prompt-with-document inputs; local result persistence; command-line, interactive terminal, and local agent-tool access; synchronous and asynchronous execution; workspace preparation; folder-to-document preparation; session health and recovery guidance; concurrent-run isolation; diagnostics and run observability.
- **Out of scope**: automation of other model providers; official model API clients; hosted multi-tenant service operation; bypassing CAPTCHAs, access controls, subscriptions, or provider limits; account creation or credential management; evaluating the factual quality of model answers; editing a user's source files from model output; guaranteeing availability when `chat.qwen.ai` is unavailable.

## Feature Requirements

### P0 — Must Have

- **F-001 — Direct prompt execution**: A user can submit non-empty text and receive one terminal success or explicit failure outcome. Acceptance: a direct-text acceptance run returns a complete result location on success and a reason plus recovery action on failure.
- **F-002 — Prompt-file execution**: A user can submit a readable local prompt file without manually copying its contents into the website. Acceptance: the accepted file's full prompt is represented in the completed run, while a missing or unreadable file is rejected before submission.
- **F-003 — Prompt with document execution**: A user can submit one prompt together with one supported local document. Acceptance: the run does not send the prompt until the document is reported ready, and an unusable document produces an explicit failure. The attachment must satisfy the Product-approved format and exact-byte size matrix linked to F-003: the byte ceiling is `104857600` bytes (`100 * 1024 * 1024`) and the supported extension allowlist is enforced by the shared pre-flight validation utility; each rejected boundary case (zero bytes, exact maximum, maximum + 1 byte, unreadable file, unsupported format, type/content mismatch) has a specified pre-flight validation stage and a stable failure reason, and no unsupported input ever reaches the provider.
- **F-004 — Authenticated session handling**: A user can establish, check, and reuse a local authenticated session without exposing its contents in normal output. Acceptance: a valid saved session permits a headless acceptance run, while an invalid session returns an authentication-required outcome with a login action.
- **F-005 — Isolated conversation context**: Every new run starts without prior conversation content affecting its request. Acceptance: two sequential acceptance runs with contradictory context produce run records showing that each began in a new conversation.
- **F-006 — Complete response detection**: A run waits for a terminal response rather than treating partial streaming text as complete. Acceptance: a fixture that pauses mid-response yields no success until generation ends, and a run exceeding its time budget yields an explicit timeout.
- **F-007 — Durable local results**: A successful run stores the complete response and a traceable run record without leaving a partial destination after interrupted persistence. Acceptance: forced interruption during saving leaves either the prior complete destination or the new complete destination, never a truncated success artifact.
- **F-008 — Safe local path boundaries**: Agent-initiated file work remains within the operator-approved workspace. Acceptance: an input or output path resolving outside that workspace is rejected before any external submission or local write.

### P1 — Should Have

- **F-009 — Asynchronous job control**: An agent can queue a long-running prompt, receive a tracking identifier, and later retrieve a terminal state. Acceptance: a queued acceptance run returns its identifier within the Goal 4 target and polling eventually returns completed or failed.
- **F-010 — Concurrent-run isolation**: Multiple accepted runs progress independently within configured resource limits. Acceptance: the Goal 5 isolation exercise completes every unaffected run despite one forced failure.
- **F-011 — Folder prompt preparation**: A user can turn a supported local folder into one ordered prompt document while preserving resolvable local references. Acceptance: a fixture folder compiles deterministically and reports every unresolved or out-of-bound reference.
- **F-012 — Workspace readiness diagnostics**: A user can check whether local prerequisites, authentication, workspace access, and output access are ready before starting work. Acceptance: each deliberately missing prerequisite is reported separately with one corrective action and a non-success outcome.
- **F-013 — Interactive terminal operation**: A person at a terminal can configure and monitor multiple prompt runs without memorizing command syntax. Acceptance: the operator can start, distinguish, and review the terminal state of at least two runs using only the interactive interface.

### P2 — Nice to Have

- **F-014 — Optional external observability**: An operator can forward run health and failure information to a configured monitoring destination without making that destination mandatory. Acceptance: a configured acceptance run emits monitoring data, while an unavailable destination does not prevent the run from reaching its own terminal outcome.
- **F-015 — Guided product updates**: An operator can check for an available release and preview the proposed change before approving it. Acceptance: a preview reports the current and proposed versions without changing installed files.
- **F-016 — Machine-readable diagnostics**: Automated clients can consume readiness and failure reports without parsing human prose. Acceptance: every diagnostic outcome in the acceptance matrix can be decoded into a stable status, issue, and suggested action.

## Non-functional Requirements (High-level)

| Category | Commitment | Detail lives in |
|----------|------------|-----------------|
| Reliability | Accepted work reaches one explicit terminal outcome, and unrelated runs remain isolated | [Prompt FRD](modules/prompt/FRD.md) for F-005–F-007 and F-010 |
| Performance | User-facing submission and monitoring remain responsive during long work | [Prompt FRD](modules/prompt/FRD.md) for F-006 and F-009 |
| Security & privacy | Sessions and generated artifacts remain local by default, sensitive values are not emitted, and workspace boundaries are enforced | [Session FRD](modules/session/FRD.md) for F-004 and F-008; [Prompt FRD](modules/prompt/FRD.md) for F-007 |
| Compatibility | Primary workflows expose equivalent outcomes to people and local agent clients | [CLI DESIGN](modules/cli/DESIGN.md) and [MCP DESIGN](modules/mcp/DESIGN.md) |
| Maintainability | Upstream website changes fail explicitly and can be reproduced with controlled acceptance scenarios | [Prompt FRD](modules/prompt/FRD.md) for F-003 and F-006 |
| Accessibility | Interactive operation remains understandable without color-only status or memorized commands | [CLI DESIGN](modules/cli/DESIGN.md) for F-013 |

### Requirement Ownership Map

Every F-00x requirement maps to a current owning document. Shared ownership is allowed where noted; the owning document wins on a requirement conflict. For cross-feature behavior, Product owns the business outcome and Engineering owns the enforcement point.

| Requirement | Owning document | Notes |
|---|---|---|
| F-001 Direct prompt execution | [Prompt FRD](modules/prompt/FRD.md) FR-PROMPT-001 | CLI and MCP surfaces inherit via [CLI DESIGN](modules/cli/DESIGN.md) and [MCP DESIGN](modules/mcp/DESIGN.md) |
| F-002 Prompt-file execution | [Prompt FRD](modules/prompt/FRD.md) FR-PROMPT-002 | — |
| F-003 Prompt with document execution | [Prompt FRD](modules/prompt/FRD.md) FR-PROMPT-003 + shared pre-flight validation | Supported-format allowlist and exact-byte ceiling are shared by CLI/MCP |
| F-004 Authenticated session handling | [Session FRD](modules/session/FRD.md) FR-SESSION-001 / FR-SESSION-004 | Health verdicts, reasons, and recovery actions |
| F-005 Isolated conversation context | [Prompt FRD](modules/prompt/FRD.md) | — |
| F-006 Complete response detection | [Prompt FRD](modules/prompt/FRD.md) FR-PROMPT-006 | — |
| F-007 Durable local results | [Prompt FRD](modules/prompt/FRD.md) + [Logging module](modules/logging/BACKLOG.md) | Run records and response persistence |
| F-008 Safe local path boundaries | [Session FRD](modules/session/FRD.md) + [MCP hardening](modules/mcp/BACKLOG.md) | Workspace root enforcement on both surfaces |
| F-009 Asynchronous job control | [Prompt FRD](modules/prompt/FRD.md) + [Jobs module](modules/jobs/BACKLOG.md) | Shared by CLI/MCP |
| F-010 Concurrent-run isolation | [Prompt FRD](modules/prompt/FRD.md) + [Swarm module](modules/swarm/BACKLOG.md) | — |
| F-011 Folder prompt preparation | [Prompt FRD](modules/prompt/FRD.md) + [Jobs module](modules/jobs/BACKLOG.md) | Folder compilation |
| F-012 Workspace readiness diagnostics | [CLI DESIGN](modules/cli/DESIGN.md) doctor command | — |
| F-013 Interactive terminal operation | [CLI DESIGN](modules/cli/DESIGN.md) + [TUI module](modules/tui/BACKLOG.md) | — |
| F-014 Optional external observability | [Logging module](modules/logging/BACKLOG.md) | — |
| F-015 Guided product updates | [Update module](modules/update/BACKLOG.md) | — |
| F-016 Machine-readable diagnostics | [MCP DESIGN](modules/mcp/DESIGN.md) + [CLI DESIGN](modules/cli/DESIGN.md) | Stable status/issue/action payloads |

## Open Questions / Risks

| # | Question / Risk | Owner | Deadline | Status |
|---|-----------------|-------|----------|--------|
| 1 | Which `chat.qwen.ai` account tiers and regional variants are part of the supported acceptance environment? | Product | Before the next release scope is approved | open |
| 2 | Which document types and maximum document sizes form the supported F-003 contract? | Product | Before the next F-003 acceptance review | resolved — see [Prompt FRD](modules/prompt/FRD.md) FR-PROMPT-003 and the shared pre-flight validation allowlist |
| 3 | Goal 1 acceptance protocol: record supported tier/region, service-health preflight, workflow allocation, initial attempts, retries, exclusions with reasons, sample validity, and QA approval. Unapproved protocol blocks a reliability claim. | QA | Before the next reliability report | open |
| 4 | What is the minimum supported machine profile and safe default concurrency for F-010? | Engineering | Before concurrent-run defaults are approved | open |
| 5 | How long must run records and generated results be retained by default? | Product / Security | Before retention behavior is changed | open |
| 6 | Upstream UI, authentication, or policy changes may interrupt all automation without notice. | Product / Engineering | Review before every release | open |
| 7 | Provider terms may restrict some automated usage patterns even when the product is technically able to perform them. | Legal / Product | Before public distribution decisions | resolved — see docs/MULTI_ACCOUNT_ROTATION.md policy gate (2026-10-18, Raka) |
| 8 | Which accessibility standard and terminal environments define acceptance for F-013? | Design | Before the next interactive-interface review | open |
