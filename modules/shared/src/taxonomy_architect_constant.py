"""Taxonomy: architect role prompt template constant.

Domain taxonomy constant layer for the built-in Architect prompt template.
"""

from __future__ import annotations

EMBEDDED_ARCHITECT_TEMPLATE: str = r"""# Plan: {feature} — Architect

## Summary

{One paragraph describing the architecture review scope.}

## Findings

### Layer Boundaries
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Responsibility segregation, dependency direction, interface abstraction, layer skipping, circular dependencies -->

### Naming
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Domain terminology consistency, acronym expansion, meaningful abbreviations, naming patterns, context clarity -->

### Orphan
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Unused classes/interfaces, dead code paths, unreachable modules, orphaned configuration, disconnected components -->

### Scalability
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Horizontal scaling readiness, stateless design, bottleneck identification, resource contention, load distribution patterns -->

### Data Flow
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Synchronous/asynchronous boundaries, backpressure handling, data validation points, transformation consistency, pipeline integrity -->

## Violations

{List or "None"}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level | Meaning |
| ------- | ------------------------------------------------------ |
| 🔴 CRITICAL | Layering breach, security, data leak. Immediate fix. |
| 🟡 WARNING | Convention/perf/maintainability. Fix this cycle. |
| 🟢 INFO | Suggestion. Deferrable. |
"""

__all__ = ["EMBEDDED_ARCHITECT_TEMPLATE"]
