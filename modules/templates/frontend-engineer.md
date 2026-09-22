As a Frontend Engineer agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Frontend Engineer scope below.

Issue Section Template
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}

- **Title**: \[FE\][{Severity}\] {concise issue title}
- **Label**: {ui|state|api-client|performance|a11y|test|severity-critical|severity-warning|severity-info}
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

- **Open Questions**: {list of open questions, or "None"}

FullTemplate
```markdown
# Plan: {feature} — Frontend Engineer

## Summary
{One paragraph describing the frontend implementation scope, affected user interfaces, client state changes, API integrations, and readiness of the client side code for deployment.}

### Scope 1: Implement the client side user interface components
<!-- Check component structure, reusability, props interface, semantic HTML, design system adherence, and visual rendering accuracy -->
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 2: Manage the client side application state
<!-- Check state initialization, state updates, local versus global state boundaries, data synchronization, and memory leak prevention -->
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 3: Consume the backend API and handle client errors
<!-- Check API request execution, response parsing, loading state handling, client side error display, retry mechanisms, and optimistic updates -->
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 4: Tune the frontend performance and responsiveness
<!-- Check render latency, unnecessary re-renders, bundle size impact, responsive layout adaptation, input responsiveness, and resource loading strategy -->
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 5: Write the frontend unit and component tests
<!-- Check component rendering tests, user interaction simulation, state change verification, mock API integration, and test coverage metrics -->
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue FE-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Code

{Grouped by file or component}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Broken user interface, unhandled client crash, state corruption, or severe accessibility failure. Immediate fix. |

| WARNING | Performance lag, poor error handling, inconsistent design system usage, or missing test coverage. Fix this cycle. |

| INFO | Code readability, minor refactoring, or visual polish. Deferrable. |
```
