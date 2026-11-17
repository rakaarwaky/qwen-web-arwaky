# PRD — qwen-web-arwaky

## Project Overview

qwen-web-arwaky is a Python CLI and MCP server that automates `chat.qwen.ai` through a persistent authenticated browser session, without a paid model API key. Developers, local automation operators, and AI agents submit substantial prompts and documents to `chat.qwen.ai`; the product sends the prompt, waits for the terminal response, extracts it, and saves the result locally with a traceable run record.

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Independent developer without an API budget | submit large local prompts and documents at no API cost | I get a complete, auditable response stored at a known location without a paid key | P0 |
| AI coding agent over a local tool connection | receive machine-readable acceptance, progress, success, and failure responses | I can drive unattended runs and resolve interactive state by action, not by observing a browser | P0 |
| Automation operator running unattended jobs | get isolated runs with bounded waiting and actionable diagnostics | I can trust that every submitted job reaches an auditable terminal state without inspecting each open session | P1 |
| Developer maintaining automation after an upstream change | get explicit, reproducible failures instead of partial content | I can demonstrate a regression and pin the repair without risking user data | P1 |

## Goals

- **Reliable prompt workflows**: at least 99 of 100 acceptance runs across direct text, prompt file, and prompt-plus-document workflows reach a successful terminal outcome, with every failure reported explicitly.
- **Complete audit trail**: 100% of successful runs carry both a readable result file and a corresponding run record.
- **Cross-surface equivalence**: all 3 primary prompt workflows produce the same success, failure, and result-location information on both the command-line and agent-tool surfaces.
- **Responsive async submission**: p95 elapsed time from accepted submission to receipt of a tracking identifier is at or below 2 seconds across 30 queued-run trials.
- **Concurrent-run isolation**: in a ten-run exercise with one forced failure, all 9 unaffected runs reach their own terminal outcome.

### Goals & Success Metrics

| # | Goal | Measurement | Target |
|---|------|-------------|--------|
| 1 | Complete prompt workflows reliably under controlled service availability | A 100-run acceptance exercise covering direct text, prompt files, and prompt-plus-document runs | At least 99 successful terminal outcomes out of 100 runs, with every failure reported explicitly |
| 2 | Preserve every accepted result and its audit trail | Compare terminally successful runs with readable result files and corresponding run records | 100% of successful runs have both artifacts |
| 3 | Give command-line and agent clients equivalent access to the primary prompt workflows | Cross-surface acceptance matrix for direct text, prompt files, and prompt-plus-document runs | 3 of 3 workflows produce the same success, failure, and result-location information on both surfaces |
| 4 | Keep asynchronous agent calls responsive during long generations | Measure elapsed time from accepted submission to receipt of a tracking identifier in 30 queued-run trials | p95 at or below 2 seconds |
| 5 | Prevent one failed parallel run from terminating unrelated work | Ten-run isolation exercise with one forced authentication or generation failure | All 9 unaffected runs reach their own terminal outcome |

**Goal 1 acceptance protocol:** Before a reliability claim is made for Goal 1, a QA-approved versioned sampling protocol must be on record that states: the supported account tier and region, service-health preconditions that must hold before sampling, the workflow allocation across the 100 runs, how many initial attempts are made, how retries are counted, which exclusions are valid and why, what makes a sample valid, and the QA approval signature. An unapproved protocol blocks the reliability claim. The existing 100-run / 99-success target remains in force.

## Non-Goals

- Automation of other model providers, and official model API clients.
- Hosted multi-tenant service operation.
- Bypassing CAPTCHAs, access controls, subscriptions, or provider limits.
- Account creation or credential management.
- Evaluating the factual quality of model answers.
- Editing a user's source files from model output.
- Guaranteeing availability when `chat.qwen.ai` is unavailable.

## Target Users

| Persona | Need | Current Pain | Desired Outcome |
|---------|------|--------------|-----------------|
| Independent developer working without an API budget | Send large local prompts and documents at no API cost | Cannot supervise every browser interaction; job not "done" until a complete response is stored at a known location with a traceable run record | A complete response stored at a known location with a traceable run record, at no API cost |
| AI coding agent operating through a local tool connection | Predictable machine-readable acceptance, progress, success, and failure responses | Cannot solve interactive challenges or infer state from a visible browser | Predictable machine-readable responses it can act on without observing a browser |
| Automation operator running unattended jobs overnight | Isolated runs, bounded waiting, and actionable diagnostics | Cannot inspect each open session; success is uncertain when any job fails | Every submitted job reaches an auditable terminal state, with isolation and recovery guidance |
| Developer maintaining automation after an upstream website change | Failures that are explicit and reproducible | Upstream changes silently produce partial content | A regression can be demonstrated and pinned without risking user data |

## Scope

### In Scope

- Local automation of authenticated `chat.qwen.ai` prompt workflows; direct-text, prompt-file, and prompt-with-document inputs; local result persistence.
- Command-line, interactive terminal, and local agent-tool access; synchronous and asynchronous execution.
- Workspace preparation; folder-to-document preparation; session health and recovery guidance; concurrent-run isolation; diagnostics and run observability.

### Out of Scope

- Automation of other model providers; official model API clients; hosted multi-tenant service operation.
- Bypassing CAPTCHAs, access controls, subscriptions, or provider limits; account creation or credential management.
- Evaluating the factual quality of model answers; editing a user's source files from model output; guaranteeing availability when `chat.qwen.ai` is unavailable.

---

## Project Requirements

### PR-QWA-001: Direct prompt execution — browser

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | submit non-empty text and get one terminal success or explicit failure outcome | I know where the result was saved or what to do next | P0 |

#### Proposed Solution

A direct-text acceptance run returns a complete result location on success and a reason plus recovery action on failure.

#### Main User Flow

1. Submit a non-empty prompt.
2. Receive one terminal success or explicit failure outcome.
3. On success, the result location is reported; on failure, a reason plus recovery action is reported.

### PR-QWA-002: Prompt-file execution — cli

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | submit a readable local prompt file without copying its contents into the website | the accepted file's full prompt is represented in the completed run | P0 |

#### Proposed Solution

The accepted file's full prompt is represented in the completed run; a missing or unreadable file is rejected before submission.

#### Main User Flow

1. Reference a readable local prompt file.
2. The file's full prompt is represented in the completed run.
3. A missing or unreadable file is rejected before submission.

### PR-QWA-003: Prompt with document execution — config

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | submit one prompt together with one supported local document | the run does not send the prompt until the document is reported ready, and an unusable document produces an explicit failure | P0 |

#### Proposed Solution

The run does not send the prompt until the document is reported ready; an unusable document produces an explicit failure. The attachment must satisfy the Product-approved format and exact-byte size matrix linked to F-003: the byte ceiling is `104857600` bytes (`100 * 1024 * 1024`) and the supported extension allowlist is enforced by the shared pre-flight validation utility; each rejected boundary case (zero bytes, exact maximum, maximum + 1 byte, unreadable file, unsupported format, type/content mismatch) has a specified pre-flight validation stage and a stable failure reason, and no unsupported input ever reaches the provider.

#### Main User Flow

1. Submit a prompt with one supported local document.
2. The document is reported ready before the prompt is sent.
3. An unusable document produces an explicit failure at the pre-flight validation stage.

### PR-QWA-004: Authenticated session handling — jobs

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Automation operator | establish, check, and reuse a local authenticated session without exposing its contents in normal output | a valid saved session permits a headless acceptance run, while an invalid session returns an authentication-required outcome with a login action | P0 |

#### Proposed Solution

A valid saved session permits a headless acceptance run; an invalid session returns an authentication-required outcome with a login action.

#### Main User Flow

1. Establish a local authenticated session.
2. Reuse the saved session for a headless run.
3. An invalid session returns an authentication-required outcome with a login action.

### PR-QWA-005: Isolated conversation context — logging

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | every new run to start without prior conversation content affecting its request | two sequential acceptance runs with contradictory context produce run records showing that each began in a new conversation | P0 |

#### Proposed Solution

Every new run starts without prior conversation content affecting its request; two sequential acceptance runs with contradictory context produce run records showing that each began in a new conversation.

#### Main User Flow

1. Start a new run.
2. The run record shows it began in a new conversation.
3. A second run with contradictory context also shows a new conversation.

### PR-QWA-006: Complete response detection — mcp

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | a run to wait for a terminal response rather than treating partial streaming text as complete | a fixture that pauses mid-response yields no success until generation ends, and a run exceeding its time budget yields an explicit timeout | P0 |

#### Proposed Solution

A run waits for a terminal response; a fixture that pauses mid-response yields no success until generation ends, and a run exceeding its time budget yields an explicit timeout.

#### Main User Flow

1. Submit a prompt and wait for the response.
2. A paused stream yields no success until generation ends.
3. A run exceeding its time budget yields an explicit timeout.

### PR-QWA-007: Durable local results — prompt

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | a successful run to store the complete response and a traceable run record without leaving a partial destination after interrupted persistence | forced interruption during saving leaves either the prior complete destination or the new complete destination, never a truncated success artifact | P0 |

#### Proposed Solution

A successful run stores the complete response and a traceable run record; forced interruption during saving leaves either the prior complete destination or the new complete destination, never a truncated success artifact.

#### Main User Flow

1. Run to completion.
2. The complete response and a traceable run record are stored.
3. Forced interruption leaves either the prior or the new complete destination, never a truncated artifact.

### PR-QWA-008: Safe local path boundaries — prompt_runtime

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Automation operator | agent-initiated file work to remain within the operator-approved workspace | an input or output path resolving outside that workspace is rejected before any external submission or local write | P0 |

#### Proposed Solution

Agent-initiated file work remains within the operator-approved workspace; an input or output path resolving outside that workspace is rejected before any external submission or local write.

#### Main User Flow

1. Reference an input or output path.
2. A path inside the workspace is accepted.
3. A path resolving outside the workspace is rejected before submission or write.

### PR-QWA-009: Asynchronous job control — session

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| AI coding agent | queue a long-running prompt, receive a tracking identifier, and later retrieve a terminal state | a queued acceptance run returns its identifier within the Goal 4 target and polling eventually returns completed or failed | P1 |

#### Proposed Solution

An agent can queue a long-running prompt, receive a tracking identifier, and later retrieve a terminal state; polling eventually returns completed or failed.

#### Main User Flow

1. Queue a long-running prompt.
2. Receive a tracking identifier within the Goal 4 target.
3. Poll for the terminal state (completed or failed).

### PR-QWA-010: Concurrent-run isolation — swarm

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Automation operator | multiple accepted runs to progress independently within configured resource limits | the Goal 5 isolation exercise completes every unaffected run despite one forced failure | P1 |

#### Proposed Solution

Multiple accepted runs progress independently within configured resource limits; the Goal 5 isolation exercise completes every unaffected run despite one forced failure.

#### Main User Flow

1. Submit multiple accepted runs.
2. Force one failure.
3. Every unaffected run completes its own terminal outcome.

### PR-QWA-011: Folder prompt preparation — tui

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Developer without an API budget | turn a supported local folder into one ordered prompt document while preserving resolvable local references | a fixture folder compiles deterministically and reports every unresolved or out-of-bound reference | P1 |

#### Proposed Solution

A supported local folder compiles into one ordered prompt document while preserving resolvable local references; every unresolved or out-of-bound reference is reported.

#### Main User Flow

1. Provide a supported local folder.
2. The folder compiles into one ordered prompt document.
3. Every unresolved or out-of-bound reference is reported.

### PR-QWA-012: Workspace readiness diagnostics — update

#### User Stories

| As a | I want | So that | Priority |
|------|--------|---------|----------|
| Automation operator | check whether local prerequisites, authentication, workspace access, and output access are ready before starting work | each deliberately missing prerequisite is reported separately with one corrective action and a non-success outcome | P1 |

#### Proposed Solution

Each deliberately missing prerequisite is reported separately with one corrective action and a non-success outcome.

#### Main User Flow

1. Run the workspace readiness check.
2. Each missing prerequisite is reported separately.
3. Each report carries one corrective action and a non-success outcome.


---


## Reference

- PRD: [PRD.md](PRD.md)
- ROADMAP: [ROADMAP.md](ROADMAP.md)
- ARCHITECTURE: [ARCHITECTURE.md](ARCHITECTURE.md)
