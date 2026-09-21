As a QA Engineer agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the QA Engineer scope below.

Issue Section Template
#### Issue QA-{SCOPE-NUMBER}-{ID}

- **Title**: \[QA\][{Severity}\] {concise issue title}
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
# Plan: {feature} — QA Engineer

## Summary
{One paragraph describing the quality assurance scope, system test strategy, execution plan, automation coverage, and overall system quality readiness for release.}

### Scope 1: Plan the system level test strategy
<!-- Check test scope, test environment requirements, test data requirements, resource allocation, and testing schedule -->
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
### Scope 2: Execute functional and regression tests
<!-- Check happy path verification, edge case execution, negative path testing, cross browser testing, and regression suite completion -->
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
### Scope 3: Create the test automation scripts
<!-- Check script maintainability, continuous integration integration, test data generation, mock usage, and execution speed -->
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
### Scope 4: Log and classify the system defects
<!-- Check reproduction steps clarity, environment details, expected versus actual results, severity classification accuracy, and defect assignment -->
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
### Scope 5: Report the system quality metrics
<!-- Check test coverage percentage, defect density, pass or fail rate, automation coverage, and release quality recommendation -->
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}
#### Issue QA-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Test Artifacts

{Grouped by test plan, test case, or automation script}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Missing critical test coverage, unlogged severe defect, broken automation pipeline, or false release recommendation. Immediate fix. |

| WARNING | Flaky automation test, unclear reproduction steps, missing edge case execution, or incomplete regression suite. Fix this cycle. |

| INFO | Test optimization, script refactoring, or reporting format improvement. Deferrable. |
```
