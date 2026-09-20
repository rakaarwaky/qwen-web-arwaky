As a Product Engineer agent, read all relevant attached documents, analyze the feature delivery status, and fill this plan using the Product Engineer scope below.

Issue Section Template
#### Issue PE-{SCOPE-NUMBER}-{ID}

- **Title**: [PE][{Severity}] {concise issue title}
- **Location Path**:
  {file or section reference}
- **Description**: {detailed description of the issue}
- **Acceptance Criteria**: {how to verify the fix is done}
- **Recommendation**: {actionable fix}
- **Git Diff**:

```diff
- {old content or line}
+ {new content or line}
```

FullTemplate
```markdown
# Plan: {feature} — Product Engineer

## Summary
{One paragraph describing the product engineering scope, feature delivery tracking, cross-team alignment, gap identification, and release readiness without writing code or executing tests.}

### Scope 1: Track the feature delivery progress
<!-- Check engineering milestones, backend and frontend completion status, design handoff status, technical specification adherence, and timeline alignment -->
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
### Scope 2: Map the cross-team dependencies
<!-- Check blocking dependencies between backend and frontend, external team reliance, API contract readiness, and environment provisioning status -->
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
### Scope 3: Identify blockers and specification gaps
<!-- Check mismatches between business requirements and implementation, missing technical edge cases, unresolved architectural blockers, and unclarified technical assumptions -->
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
### Scope 4: Coordinate the demo environment preparation
<!-- Check test data availability, environment configuration status, feature toggle setup, cross-module integration status, and demo script readiness for stakeholders -->
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
### Scope 5: Verify the release candidate completeness
<!-- Check code freeze status, documentation updates, deployment artifact readiness, rollback plan availability, and release checklist sign-offs from all required roles -->
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}
#### Issue PE-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Document

{Grouped by tracking report, checklist, or dependency map}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Unresolved blocking dependency, critical gap between requirement and code, or release candidate missing mandatory sign-offs. Immediate fix. |

| WARNING | Misaligned timeline, unclear cross-team handoff, missing demo data, or incomplete release checklist. Fix this cycle. |

| INFO | Process improvement, better tracking visibility, or documentation polish. Deferrable. |
```
