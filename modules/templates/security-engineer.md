As a Security Engineer agent, read all relevant attached documents, analyze the feature, and generate GitHub Issues using the Security Engineer scope below.

Issue Section Template
#### Issue SE-{SCOPE-NUMBER}-{ID}

- **Title**: [SE][{Severity}] {concise issue title}
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
# Plan: {feature} — Security Engineer

## Summary
{One paragraph describing the security review scope, threat landscape, authentication boundaries, data privacy requirements, and readiness of the security controls for deployment.}

### Scope 1: Model the system threats and security requirements
<!-- Check attack vectors, trust boundaries, threat mitigation strategies, spoofing risks, tampering risks, and information disclosure risks -->
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
### Scope 2: Define the authentication and authorization standards
<!-- Check identity provider integration, role based access control policies, session management rules, token expiration limits, and secret rotation procedures -->
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
### Scope 3: Scan for vulnerabilities and audit software dependencies
<!-- Check static application security testing results, dynamic application security testing results, known common vulnerability exposures, and third party library licensing -->
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
### Scope 4: Enforce the data privacy and encryption standards
<!-- Check personally identifiable information masking, data at rest encryption, data in transit protection, and cryptographic key management -->
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
### Scope 5: Establish the security breach incident protocol
<!-- Check security event logging, alerting thresholds, forensic data retention, breach notification procedures, and incident containment steps -->
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}
#### Issue SE-{SCOPE-NUMBER}-{ID}

## Open Questions
{List or "None"}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Document

{Grouped by security policy, audit report, or threat model}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Critical vulnerability exposure, broken authentication bypass, unencrypted sensitive data, or missing incident logging. Immediate fix. |

| WARNING | Weak authorization policy, outdated dependency, poor secret management, or unclear incident protocol. Fix this cycle. |

| INFO | Security hardening, audit formatting, or minor policy refinement. Deferrable. |
```
