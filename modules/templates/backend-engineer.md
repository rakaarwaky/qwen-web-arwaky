As a Backend Engineer agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Backend Engineer scope below.

Issue Section Template
#### Issue BE-{SCOPE-NUMBER}-{ID}

- **Title**: [BE][{Severity}] {concise issue title}
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
# Plan: {feature} — Backend Engineer

## Summary
{One paragraph describing the backend implementation scope, affected services, database changes, API integrations, and readiness of the server side code for deployment.}

### Scope 1: Implement the server side API
<!-- Check endpoint routing, request parsing, response formatting, error handling, input validation, HTTP method usage, and API contract adherence -->
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
### Scope 2: Build the physical database schema
<!-- Check table creation, column types, indexing strategy, foreign keys, constraints, migration scripts, and query execution plans -->
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
### Scope 3: Enforce the business rules in server code
<!-- Check domain logic implementation, transaction boundaries, data consistency, state transitions, concurrency control, and authorization checks -->
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
### Scope 4: Tune the backend service performance
<!-- Check N plus 1 queries, memory allocation, blocking IO, caching strategy, algorithmic complexity, connection pooling, and timeout configurations -->
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
### Scope 5: Write the backend test code
<!-- Check unit test coverage, integration test scenarios, mock external dependencies, test data setup, edge case verification, and continuous integration readiness -->
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}
#### Issue BE-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Code

{Grouped by file or module}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Security vulnerability, data corruption, broken transaction, or API contract violation. Immediate fix. |

| WARNING | Performance bottleneck, missing test coverage, poor error handling, or weak database indexing. Fix this cycle. |

| INFO | Code readability, minor refactoring, or nice to have optimization. Deferrable. |
```
