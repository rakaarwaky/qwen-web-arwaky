As a DevOps engineer agent, read all relevant attached documents, analyze the infrastructure and delivery requirements, and fill this plan using the DevOps scope below.

Issue Section Template
#### Issue DO-{SCOPE-NUMBER}-{ID}

- **Title**: \[DO\][{Severity}\] {concise issue title}
- **Label**: {ci|container|deploy|logging|config|severity-critical|severity-warning|severity-info}
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
# Plan: {feature} — DevOps Engineer

## Summary
{One paragraph describing the infrastructure scope, delivery pipeline, deployment strategy, observability setup, and operational readiness for the feature release.}

### Scope 1: Configure the continuous integration and deployment pipeline
<!-- Check build reproducibility, lint and test gates, artifact packaging, dependency caching, deployment triggers, and pipeline execution speed -->
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
### Scope 2: Provision the infrastructure and environment configurations
<!-- Check infrastructure as code templates, environment variable injection, secrets management integration, resource limits, and auto-scaling policies -->
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
### Scope 3: Execute the application deployment and release rollbacks
<!-- Check deployment strategy, zero downtime requirements, database migration execution, rollback mechanisms, and release safety checks -->
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
### Scope 4: Configure system observability and uptime monitoring
<!-- Check metric collection, log aggregation, distributed tracing, alerting rules, dashboard setup, and service level objective definitions -->
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
### Scope 5: Respond to infrastructure and operational incidents
<!-- Check on-call routing, operational runbooks, disaster recovery procedures, backup verification, and incident post-mortem tracking -->
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}
#### Issue DO-{SCOPE-NUMBER}-{ID}

## Violations

{List or "None"}

## Action Items

- [ ] {Priority} {Item}

## Fixed Configuration

{Grouped by pipeline script, infrastructure template, or monitoring rule}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Pipeline failure, infrastructure outage, missing rollback plan, or blind spot in production monitoring. Immediate fix. |

| WARNING | Flaky deployment, missing alert threshold, poor resource limits, or incomplete operational runbook. Fix this cycle. |

| INFO | Cost optimization, pipeline speed improvement, or dashboard refinement. Deferrable. |
```
