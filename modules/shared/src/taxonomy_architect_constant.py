"""Taxonomy: architect role prompt template constant.

Generic architecture review prompt template — no framework coupling.
"""

from __future__ import annotations

EMBEDDED_ARCHITECT_TEMPLATE: str = r"""# Plan: {feature} — Architecture Review

## Summary

{One paragraph describing the architecture review scope.}

## Findings

### Structural Boundaries
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Module ownership, dependency direction, abstraction layers, circular dependencies, responsibility segregation -->

### Naming & Conventions
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Domain terminology, naming consistency, meaningful abbreviations, pattern adherence, context clarity -->

### Dead Code & Orphans
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Unused classes/interfaces, dead code paths, unreachable modules, orphaned configuration, disconnected components -->

### Scalability & Performance
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Stateless design, bottleneck identification, resource contention, load distribution, horizontal scaling readiness -->

### Data Flow & Integrity
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Sync/async boundaries, backpressure handling, validation points, transformation consistency, pipeline integrity -->

### Security
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Input validation, auth boundaries, secrets handling, dependency supply chain, data exposure -->

## Violations

{List or "None"}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level | Meaning |
| ------- | ------------------------------------------------------ |
| CRITICAL | Layering breach, security risk, data leak. Immediate fix. |
| WARNING | Convention/perf/maintainability. Fix this cycle. |
| INFO | Suggestion. Deferrable. |
"""

__all__ = ["EMBEDDED_ARCHITECT_TEMPLATE"]
