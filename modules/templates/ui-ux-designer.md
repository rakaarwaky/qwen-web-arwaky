As a UI/UX Designer agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the UI/UX Designer scope below.

Issue Section Template
#### Issue UX-{SCOPE-NUMBER}-{ID}

- **Title**: [UX][{Severity}] {concise issue title}
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
# Plan: {feature} — UI/UX Designer

## Summary
{One paragraph describing the user experience scope, target users, affected user journey, interface expectations, and readiness of the design specification for implementation.}

### Scope 1: Map the user journey
<!-- Check user goal, persona, entry point, task flow, interaction path, navigation logic, drop off risk, and alignment with business process -->
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
### Scope 2: Produce the wireframe prototype
<!-- Check low fidelity wireframe, high fidelity prototype, visual hierarchy, layout structure, responsive behavior, interaction affordance, and user feedback loop -->
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
### Scope 3: Define the design system
<!-- Check design tokens, color palette, typography scale, spacing scale, component library, iconography, visual assets, and consistency across screens -->
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
### Scope 4: Specify inclusive usability requirements
<!-- Check accessibility standard, keyboard support, screen reader support, color contrast, target size, cognitive load, discoverability, and usability heuristic compliance -->
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
### Scope 5: Define interface state behavior
<!-- Check loading state, empty state, error state, success state, partial data state, disabled state, retry behavior, and feedback clarity -->
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}
#### Issue UX-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Design

{Grouped by screen or component}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Broken user flow, inaccessible experience, missing critical state, or design that risks user error and data loss. Immediate fix. |

| WARNING | Usability friction, inconsistent design system, missing feedback, unclear prototype, or incomplete state handling. Fix this cycle. |

| INFO | Visual polish, microinteraction, or nice to have improvement. Deferrable. |
```
