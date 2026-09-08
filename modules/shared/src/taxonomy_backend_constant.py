"""Taxonomy: backend/tech-lead role prompt template constant.

Domain taxonomy constant layer for the built-in Backend/Tech Lead prompt template.
"""

from __future__ import annotations

EMBEDDED_BACKEND_TEMPLATE: str = r"""# Plan: {feature} — Tech Lead

## Summary

{One paragraph describing the scope of the review target.}

## Findings

### Security
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Input validation, injection (SQL/command/XSS), authentication & authorization, secrets handling, rate limiting, dependency CVEs -->

### Performance
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: N+1 queries, missing indexes, unnecessary allocations, blocking I/O, caching strategy, algorithmic complexity -->

### Error Handling
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Exception swallowing, error propagation, retry/timeout policy, graceful degradation, meaningful error messages, cleanup on failure -->

### SOLID
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Single responsibility, open/closed extension points, Liskov substitutability, interface segregation, dependency inversion -->

### Code Quality
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Duplication, dead code, complexity hotspots, type safety, lint suppressions, test coverage gaps -->

### Maintainability
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Module cohesion, coupling between layers, documentation accuracy, configurability, ease of onboarding, tech debt markers -->

## Violations

{List or "None"}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level | Meaning |
| ------- | ------------------------------------------------------------------- |
| CRITICAL | Security vuln, data leak, crash risk. Immediate fix. |
| WARNING | Perf bottleneck, SOLID violation, bypass pattern. Fix this cycle. |
| INFO | Nice-to-have. Deferrable. |
"""

__all__ = ["EMBEDDED_BACKEND_TEMPLATE"]
