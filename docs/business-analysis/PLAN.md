# Plan: Qwen Web prompt workflows and session rotation — Business Analyst

## Summary
Review of authenticated prompt execution and multi-account session rotation at commit `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Developers, automation operators and local agent clients need reliable, auditable results without ambiguous recovery or unsupported provider-policy assumptions. Existing requirements supply personas and measurable goals, but session outcome rules, supported-input boundaries, ownership links and release evidence are not yet aligned. Requirements are not ready for unconditional release sign-off. This is a static document/code review; no live Qwen UAT or legal determination was performed. No attachments were supplied; repository documents were used.

## Review basis

Reviewed PRD.md, UAT.md, ROADMAP.md, README.md, AGENTS.md, ISSUE.md, TEST.md, docs/README.md, both multi-account proposals, the rate-limit runbook, session/prompt FRDs, session backlog, MCP design, session health/rotation implementations and session value objects. Checked existing GitHub issue titles and relevant prior BA bodies; findings distinguish current gaps from closed historical reports. Git Diff blocks below are proposed requirement wording, not applied implementation changes. Owner approvals and policy decisions remain open.

### Scope 1: Define the business problem

#### Issue BA-1-001-20261018T075054Z

Title: [BA][WARNING] Define the controlled-service acceptance environment

Label: acceptance, severity-warning

Location Path:
PRD.md — Goals & Success Metrics, Goal 1; Open Questions / Risks rows 1 and 3

Description: Goal 1 now has a concrete 100-run/99-success target, but account tiers, regional variants, and controlled-service conditions remain explicitly open. A release can pass or fail depending on which runs are excluded or retried. This is a remaining acceptance-design gap, not the old missing-metrics-store finding in closed #273.

Acceptance Criteria:
- [ ] Approve the supported account/region matrix and service-health preconditions before sampling.
- [ ] Define workflow allocation, run eligibility, retry accounting, upstream-outage exclusions, and invalid-sample handling.
- [ ] A worked sample reports all 100 initial attempts, exclusions and retries separately, with reproducible pass/fail calculation and QA approval.

Recommendation: Product and QA should approve a versioned sampling protocol linked from Goal 1; keep the existing target unless an explicit scope decision changes it.

Git Diff (proposed requirement change, not applied):

```diff
- | 3 | What controlled-service conditions must hold before the Goal 1 reliability sample is considered valid? | QA | Before the next reliability report | open |
+ Goal 1 acceptance protocol: record supported tier/region, service-health preflight, workflow allocation, initial attempts, retries, exclusions with reasons, sample validity, and QA approval. Unapproved protocol blocks a reliability claim.
```

Open Questions: Which tiers and regions must be qualified? What evidence invalidates a sample rather than counting as product failure?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/601

### Scope 2: Model the business process

#### Issue BA-2-001-20261018T075054Z

Title: [BA][WARNING] Distinguish session expiry and probe failures from rate limiting

Label: business-rule, severity-warning

Location Path:
modules/session/src/capabilities_session_health_checker.py — check_session, check_all_sessions, check_pool_sync; modules/shared/src/session/taxonomy_session_vo.py — SessionStatus; PRD.md F-004

Description: The health checker reduces expired authentication, browser launch failures, network errors and timeouts to False; pool updates turn every False into LIMITED. Operators therefore see a quota verdict when re-login or environment repair is required. The rotation adapter also persists these false quota classifications. This is directly observable in the code, not a claim that live accounts were tested.

Acceptance Criteria:
- [ ] Approve distinct business outcomes for authenticated-ready, confirmed quota limit, authentication-required, and indeterminate probe failure.
- [ ] Fixtures for expired login, limit banner, launch failure, network failure and timeout retain the correct reason and recovery action.
- [ ] Only an observed provider-limit signal persists a quota-limited verdict; transient probe failure does not overwrite it with invented quota evidence.
- [ ] CLI/MCP health responses expose the approved outcome and actionable recovery without session secrets.

Recommendation: Extend the health-result contract with a reasoned verdict, then update persistence, rotation and surfaces together. Do not infer quota exhaustion from an arbitrary exception.

Git Diff (proposed requirement change, not applied):

```diff
- new_status = SessionStatus.ACTIVE if healthy else SessionStatus.LIMITED
+ Persist ACTIVE only for a successful authenticated probe; persist LIMITED only for confirmed quota evidence; report authentication-required or indeterminate with its recovery action otherwise.
```

Open Questions: Should expiry and transient failures be new stored states or a separate reason field? When may indeterminate sessions be probed again?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/602

#### Issue BA-2-002-20261018T075054Z

Title: [BA][WARNING] Resolve contradictory all-sessions-exhausted behavior

Label: process, severity-warning

Location Path:
modules/session/FRD.md — FR-SESSION-002 and Integration Points; modules/session/BACKLOG.md — SESSION-02; docs/MULTI_ACCOUNT_ROTATION.md — Rotation Logic; modules/session/src/capabilities_session_rotation_adapter.py — rotate

Description: The FRD says an all-limited pool rotates back to its first session, the integration table says no healthy session fails before browser launch, the proposal raises AllSessionsLimitedError, and rotate returns an empty response. These imply different retry and operator flows. SESSION-02 already records the unresolved policy; this issue supplies its business acceptance contract rather than asserting a newly discovered implementation bug.

Acceptance Criteria:
- [ ] Product and Engineering select one terminal/retry behavior and link the decision to SESSION-02.
- [ ] Empty, single-limited, all-limited, excluded-all and mixed pools have explicit outcomes and recovery guidance.
- [ ] An exhausted pool never silently submits through a known-limited profile; every accepted job reaches its own documented terminal or bounded deferred state.
- [ ] FRD, proposal, adapter contract and surface tests agree; any retry budget and cooldown source are documented.

Recommendation: Prefer an explicit no-eligible-session outcome before submission, with bounded recovery and no unsupported promise that quota resets tomorrow; confirm the choice with Product.

Git Diff (proposed requirement change, not applied):

```diff
- A rate-limited session is skipped in favor of a healthy one; a pool with only rate-limited sessions rotates back to the first and reports the throttle.
+ A rate-limited session is skipped. If no eligible session remains, return an explicit no-eligible-session outcome without submitting; apply only the stakeholder-approved bounded recovery policy.
```

Open Questions: Fail immediately or defer with a deadline? How is a provider reset time learned when none is supplied?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/603

### Scope 3: Formulate acceptance criteria

#### Issue BA-3-001-20261018T075054Z

Title: [BA][WARNING] Publish a testable supported-document contract for F-003

Label: acceptance, severity-warning

Location Path:
PRD.md — F-003 and Open Questions / Risks row 2; modules/prompt/FRD.md — FR-PROMPT-003; UAT.md — UAT-BA-004

Description: F-003 promises a supported document, but Product still lists types and maximum sizes as open. The prompt FRD delegates size/type limits to the upload seam; UAT tests only above 100 MiB. Users and testers cannot determine supported formats, exact boundary behavior or whether a rejected file must be stopped before upload. This differs from closed #276, which concerned folder compilation over the attachment ceiling.

Acceptance Criteria:
- [ ] Publish an approved list of document formats, byte-size ceiling and units, and filename/content validation rules.
- [ ] Criteria cover zero bytes, exact maximum, maximum plus one byte, unreadable file, unsupported format and type/content mismatch according to the approved policy.
- [ ] Each unsupported input fails at the specified validation stage with a stable reason and no accidental provider submission.
- [ ] CLI and MCP share the supported-input matrix; UAT cases trace to F-003 and FR-PROMPT-003.

Recommendation: Have Product approve the current enforceable support contract with Engineering; specify exact bytes rather than mixing MB and MiB. Do not invent format support from examples.

Git Diff (proposed requirement change, not applied):

```diff
- The attachment must pass the size and type limits the upload seam enforces before the send.
+ The attachment must satisfy the Product-approved format and exact-byte size matrix linked to F-003; each rejected boundary case has a specified validation stage and stable failure reason.
```

Open Questions: Which types and exact byte ceiling are supported? Is content inspection required, and must rejection precede browser launch or only upload?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/604

### Scope 4: Align business stakeholders

#### Issue BA-4-001-20261018T075054Z

Title: [BA][CRITICAL] Approve provider-policy boundaries before automatic account rotation

Label: compliance, severity-critical

Location Path:
PRD.md — Scope and Open Questions / Risks row 7; docs/MULTI_ACCOUNT_ROTATION.md — Problem Statement, Core Concepts and Error Messages; docs/rate-limit.md — Recovery steps

Description: The PRD excludes bypassing provider limits and explicitly leaves provider-terms review open. The multi-account proposal describes switching accounts after daily limits and advises adding accounts, while the runbook recommends reducing throughput across profiles. Without an approved boundary, Product and Engineering can implement incompatible behavior and make unsupported distribution claims. This is an unresolved compliance decision, not a legal conclusion that rotation violates any particular terms.

Acceptance Criteria:
- [ ] Legal/Product record a dated assessment of applicable provider terms, supported usage and account ownership/authorization boundaries.
- [ ] Approve whether quota-triggered cross-account rotation is permitted, restricted or excluded; specify CAPTCHA/access-control stop behavior.
- [ ] Reconcile the rotation proposal, PRD and runbook to that decision; link an accountable approver and release gate.
- [ ] If approval is unavailable, mark the proposal unapproved and prevent the affected feature from being represented as approved for public distribution.

Recommendation: Treat the rotation document as an unapproved proposal until review; remove unconditional add-more-accounts recovery advice and document only authorized, provider-compliant operation.

Git Diff (proposed requirement change, not applied):

```diff
- **Auto-Rotation**: Transparent switching between sessions on limit detection
+ **Policy gate**: Quota-triggered cross-account rotation is an unapproved proposal pending Legal/Product review against the PRD prohibition on bypassing provider limits. Do not treat technical capability as authorization.
```

Open Questions: Which provider terms apply to the supported regions and tiers? Who owns the final distribution decision?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/605

#### Issue BA-4-002-20261018T075054Z

Title: [BA][WARNING] Restore the requirement ownership chain after the module split

Label: stakeholder, severity-warning

Location Path:
PRD.md — Condition and Non-functional Requirements; ROADMAP.md — Feature Roll-up; modules/session/FRD.md and modules/prompt/FRD.md

Description: The current PRD still routes detailed requirements to modules/core/FRD.md, modules/cli/FRD.md and modules/mcp/FRD.md, none of which exists in this checkout. ROADMAP also indexes the removed core feature while current feature FRDs live under prompt, session, jobs and other modules. Stakeholders cannot follow the declared authoritative chain to approve delivery. Closed #386 concerned older selector/tool traceability; this finding is revalidated against the current split, not inferred from historical issue status.

Acceptance Criteria:
- [ ] Every local requirement/backlog link in PRD and ROADMAP resolves to an existing intended document.
- [ ] Map F-001 through F-016 to the current owning feature or surface specification and backlog, allowing shared ownership explicitly.
- [ ] Name accountable approver roles for cross-feature behavior and define which document wins on a requirement conflict.
- [ ] A link/traceability check on the reviewed commit passes, and the owner records review of the repaired map.

Recommendation: Replace removed-core references with current feature FRDs and surface DESIGN specifications as appropriate; update the roadmap roll-up without rewriting delivery status from assumptions.

Git Diff (proposed requirement change, not applied):

```diff
- [Core FRD](modules/core/FRD.md)
+ Link each requirement to its current owning feature FRD (for example prompt/FRD.md or session/FRD.md), and surface DESIGN/backlog where no surface FRD exists; maintain an F-001–F-016 ownership map.
```

Open Questions: Are surface DESIGN files authoritative requirements, or should surface FRDs be restored? Who approves shared session/job/prompt behavior?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/606

### Scope 5: Execute user acceptance testing

#### Issue BA-5-001-20261018T075054Z

Title: [BA][WARNING] Add release UAT coverage for the current five measurable goals

Label: acceptance, severity-warning

Location Path:
UAT.md — BA verification scenarios; PRD.md — Goals & Success Metrics, Goals 1–5

Description: UAT now includes persona scenarios and deterministic BA checks, so closed #284 should not be recreated as no UAT exists. However, the current release-required table does not implement the revised PRD goal exercises: the 100-run reliability sample, 100% result/run-record reconciliation, 3-workflow CLI/MCP parity, 30-trial asynchronous p95, and ten-run fault isolation. Existing async lifecycle and metrics checks do not establish these thresholds.

Acceptance Criteria:
- [ ] Create stable UAT IDs mapping each of Goals 1–5 to preconditions, test data, steps, exact oracle and expected threshold.
- [ ] Record commit, environment, tier/region, timestamps, run IDs, redacted result evidence and measured values per execution.
- [ ] Measure asynchronous acknowledgement across 30 trials and document the p95 calculation; verify parity for all three workflows and both success/failure outcomes.
- [ ] Reconcile successful output/run records and run the ten-run isolation exercise with one forced failure.
- [ ] Document reviewer approval and release disposition for failures or unexecuted cases; do not mark live exercises passed based on unit tests.

Recommendation: Extend UAT.md with a goal-to-scenario evidence matrix. Keep protocol approval as a dependency of the reliability exercise; use controlled fixtures where appropriate and authorized live sessions for upstream-dependent claims.

Git Diff (proposed requirement change, not applied):

```diff
- The following deterministic scenarios are required for release sign-off:
+ The deterministic scenarios below and goal-linked acceptance exercises for Goals 1–5 are required for release sign-off; each records its commit, preconditions, measured result, evidence and reviewer disposition.
```

Open Questions: Who signs off the release evidence? Which live-service cases may be waived, by whom, and with what residual-risk record?

Review baseline: `4897910e5ab6e5c94e0e4e04e62314feab496a0c`. Static review only; no live UAT executed.

GitHub Issue: https://github.com/rakaarwaky/qwen-web-arwaky/issues/607

## Severity Definitions
- **CRITICAL**: Missing business requirement, wrong business flow, compliance risk, stakeholder conflict, or UAT blocker. Immediate fix.
- **WARNING**: Ambiguous requirement, incomplete acceptance criteria, missing edge case, unclear process, or missing sign-off. Fix this cycle.
- **INFO**: Documentation improvement, clarification, or optimization. Deferrable.
