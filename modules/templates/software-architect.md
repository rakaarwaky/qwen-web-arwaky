As a Software Architect agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Software Architect scope below.

Issue Section Template
#### Issue ARCH-{SCOPE-NUMBER}-{ID}

- **Title**: [ARCH][{Severity}] {concise issue title}
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
# Plan: {feature} — Software Architect

## Summary
{One paragraph describing the architectural review scope, affected system boundaries, cross-module impact, non-functional requirements, and readiness of the architectural standard for the feature.}

### Scope 1: Define system-wide module boundaries
<!-- Check module ownership, dependency direction, abstraction layers, circular dependencies, responsibility segregation, service granularity, and interface segregation -->
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
### Scope 2: Design cross-feature integration patterns
<!-- Check synchronous and asynchronous boundaries, event-driven patterns, message contracts, data consistency across modules, pipeline integrity, and backpressure handling -->
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
### Scope 3: Architect system scalability
<!-- Check stateless design, bottleneck identification, resource contention, horizontal scaling readiness, reliability targets, capacity planning, and performance baseline -->
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
### Scope 4: Govern technology standards
<!-- Check technology stack selection, naming convention, architectural pattern adherence, framework standardization, dependency policy, and security architecture baseline -->
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
### Scope 5: Manage technical debt strategy
<!-- Check debt identification, debt classification, refactoring priority, deprecation path, backward compatibility, and migration plan -->
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}
#### Issue ARCH-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Document

{Grouped by architectural decision or standard}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Layering breach, security architecture gap, scalability blocker, or uncontrolled cross-system dependency. Immediate fix. |

| WARNING | Inconsistent standard, emerging bottleneck, weak integration pattern, or growing technical debt. Fix this cycle. |

| INFO | Architectural optimization, pattern refinement, or long-term improvement. Deferrable. |
```
