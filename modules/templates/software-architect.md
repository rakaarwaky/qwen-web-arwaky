As a Software Architect agent, read all relevant attached documents, analyze the feature, and fill this plan using the Software Architect scope below.

# Plan: {feature} — Software Architect

## Summary

{One paragraph describing the architectural review scope, affected system boundaries, cross-module impact, non-functional requirements, and readiness of the architectural standard for the feature.}

## Findings

### 1. Define system-wide module boundaries

| # | Severity | Issue | Location | Recommendation |

| --- | --- | --- | --- | --- |

&lt;!-- Check module ownership, dependency direction, abstraction layers, circular dependencies, responsibility segregation, service granularity, and interface segregation --&gt;

### 2. Design cross-feature integration patterns

| # | Severity | Issue | Location | Recommendation |

| --- | --- | --- | --- | --- |

&lt;!-- Check synchronous and asynchronous boundaries, event-driven patterns, message contracts, data consistency across modules, pipeline integrity, and backpressure handling --&gt;

### 3. Architect system scalability

| # | Severity | Issue | Location | Recommendation |

| --- | --- | --- | --- | --- |

&lt;!-- Check stateless design, bottleneck identification, resource contention, horizontal scaling readiness, reliability targets, capacity planning, and performance baseline --&gt;

### 4. Govern technology standards

| # | Severity | Issue | Location | Recommendation |

| --- | --- | --- | --- | --- |

&lt;!-- Check technology stack selection, naming convention, architectural pattern adherence, framework standardization, dependency policy, and security architecture baseline --&gt;

### 5. Manage technical debt strategy

| # | Severity | Issue | Location | Recommendation |

| --- | --- | --- | --- | --- |

&lt;!-- Check debt identification, debt classification, refactoring priority, deprecation path, backward compatibility, and migration plan --&gt;

## Open Questions

{List or "None"}

## Violations

{List or "None"}

## Action Items

- \[ \] {Priority} {Item}

## Fixed Document

{Grouped by architectural decision or standard}

## Severity

| Level | Meaning |

| --- | --- |

| CRITICAL | Layering breach, security architecture gap, scalability blocker, or uncontrolled cross-system dependency. Immediate fix. |

| WARNING | Inconsistent standard, emerging bottleneck, weak integration pattern, or growing technical debt. Fix this cycle. |

| INFO | Architectural optimization, pattern refinement, or long-term improvement. Deferrable. |  
