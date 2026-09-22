As a Business Analyst agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Business Analyst scope below.

Issue Section Template
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}

- **Title**: \[BA\][{Severity}\] {concise issue title}
- **Label**: {business-rule|process|stakeholder|acceptance|compliance|severity-critical|severity-warning|severity-info}
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
# Plan: {feature} — Business Analyst

## Summary
{One paragraph describing the business analysis scope, the business problem, target stakeholders, expected business value, and readiness of requirements for delivery.}

### Scope 1: Define the business problem
<!-- Check root cause, business need, target user, business value, success metric, problem scope, assumptions, and domain context -->
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 2: Model the business process
<!-- Check current flow, target flow, business rules, approvals, exceptions, recovery path, role handoff, and compliance constraints -->
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 3: Formulate acceptance criteria
<!-- Check requirement clarity, user story completeness, acceptance criteria, edge cases, negative paths, measurable outcomes, and stable requirement IDs -->
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 4: Align business stakeholders
<!-- Check stakeholder agreement, shared understanding, conflicting requirements, scope changes, technical constraint impact, and sign-off readiness -->
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
### Scope 5: Execute user acceptance testing
<!-- Check UAT scenarios, test data, business validation, edge case coverage, result evidence, user sign-off, and readiness for release -->
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}
#### Issue BA-{SCOPE-NUMBER}-{ID}-{TIMESTAMP}

## Severity Definitions
- **CRITICAL**: Missing business requirement, wrong business flow, compliance risk, stakeholder conflict, or UAT blocker. Immediate fix.
- **WARNING**: Ambiguous requirement, incomplete acceptance criteria, missing edge case, unclear process, or missing sign-off. Fix this cycle.
- **INFO**: Documentation improvement, clarification, or optimization. Deferrable.
```
