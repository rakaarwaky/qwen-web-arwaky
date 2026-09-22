As a Business Analyst agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Business Analyst scope below.

Issue Section Template
#### Issue BA-{SCOPE-NUMBER}-{ID}

- **Title**: \[BA\][{Severity}\] {concise issue title}
- **Location Path**:
  {file or section reference}
- **Description**: {detailed description of the issue, including the affected business actor and expected behavior}
- **Business Benefit**: {specific value for users, stakeholders, delivery, risk reduction, or release confidence}
- **Acceptance Criteria**: {measurable conditions that prove the issue is resolved}
- **Verification**: {status: VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED; evidence, source section, test/UAT scenario, or open question}
- **Recommendation**: {actionable fix, clarification, or decision required}
- **Dependencies / Impact**: {related requirements, roles, processes, risks, or "None"}
- **Git Diff**:

```diff
- {old content or line}
+ {new content or line}
```

FullTemplate
```markdown
# Plan: {feature} — Business Analyst

## Summary
{One paragraph describing the business analysis scope, the business problem, target stakeholders, expected business value, and readiness of requirements for delivery.}

### Scope 1: Define the business problem
<!-- Check root cause, business need, target user, business value, success metric, problem scope, assumptions, and domain context -->
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
### Scope 2: Model the business process
<!-- Check current flow, target flow, business rules, approvals, exceptions, recovery path, role handoff, and compliance constraints -->
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
### Scope 3: Formulate acceptance criteria
<!-- Check requirement clarity, user story completeness, acceptance criteria, edge cases, negative paths, measurable outcomes, and stable requirement IDs -->
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
### Scope 4: Align business stakeholders
<!-- Check stakeholder agreement, shared understanding, conflicting requirements, scope changes, technical constraint impact, and sign-off readiness -->
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
### Scope 5: Execute user acceptance testing
<!-- Check UAT scenarios, test data, business validation, edge case coverage, result evidence, user sign-off, and readiness for release -->
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}
#### Issue BA-{SCOPE-NUMBER}-{ID}

## BA Issue Register and Benefits
Create a complete table containing every BA issue generated above. Do not omit issues or merge them silently. Use these columns:

| Issue ID | Severity | Issue summary | Business benefit | Verification status | Evidence / next action |
|---|---|---|---|---|---|
| BA-{SCOPE-NUMBER}-{ID} | {CRITICAL/WARNING/INFO} | {short explanation} | {why resolving it helps us} | {VERIFIED/PARTIALLY VERIFIED/NOT VERIFIED} | {evidence or action} |

After the table, explain in plain language:
1. What each issue means for the business and who is affected.
2. What benefit we get by resolving it, prioritised by CRITICAL, WARNING, then INFO.
3. Which issues can be verified from the attached documents and which require stakeholder confirmation, implementation evidence, or UAT.
4. Whether the requirements are ready for delivery, with a clear reason and a list of blockers.

## Verification Summary
- **Documents and sections reviewed**: {complete list}
- **Issues verified**: {issue IDs and evidence}
- **Issues partially verified**: {issue IDs and missing evidence, or "None"}
- **Issues not verified**: {issue IDs and reason, or "None"}
- **Recommended verification steps**: {numbered checks for stakeholder review, traceability, and UAT}
- **Overall readiness**: {READY / READY WITH CONDITIONS / NOT READY}

## Open Questions
{List or "None"}

## Severity Definitions
- **CRITICAL**: Missing business requirement, wrong business flow, compliance risk, stakeholder conflict, or UAT blocker. Immediate fix.
- **WARNING**: Ambiguous requirement, incomplete acceptance criteria, missing edge case, unclear process, or missing sign-off. Fix this cycle.
- **INFO**: Documentation improvement, clarification, or optimization. Deferrable.
```
