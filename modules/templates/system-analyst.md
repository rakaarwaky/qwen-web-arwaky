As a System Analyst agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the System Analyst scope below.

Issue Section Template
#### Issue SA-{SCOPE-NUMBER}-{ID}

- **Title**: [SA][{Severity}] {concise issue title}
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
# Plan: {feature} — System Analyst

## Summary
{One paragraph describing the system analysis scope, the feature boundaries, impacted modules, technical constraints, and readiness of the technical specification for implementation.}

### Scope 1: Specify the feature technical behavior
<!-- Check feature input and output, system behavior, processing steps, system boundaries, feature scope, technical assumptions, and impacted modules -->
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
### Scope 2: Design the logical data model
<!-- Check entity definition, key attributes, entity relationships, business constraints, data lifecycle, and CRUD operations required by the feature -->
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
### Scope 3: Design the API contract
<!-- Check endpoint definition, request and response schema, status codes, error contract, versioning, and contract between frontend backend and external systems -->
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
### Scope 4: Map the sequence diagram and edge cases
<!-- Check component interaction, happy path, failure path, timeout scenario, retry behavior, fallback path, and technical edge cases from business requirements -->
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
### Scope 5: Trace the requirement to specification
<!-- Check requirement coverage, orphan requirement detection, ambiguous requirement flag, clarification request to Business Analyst, and cross-feature impact analysis -->
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}
#### Issue SA-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Document

{Grouped by document or section}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Missing feature behavior, broken data model, incomplete API contract, or uncovered business requirement. Immediate fix. |

| WARNING | Ambiguous technical spec, missing edge case, unclear error contract, or weak traceability. Fix this cycle. |

| INFO | Specification refinement, optimization, or documentation improvement. Deferrable. |
```
