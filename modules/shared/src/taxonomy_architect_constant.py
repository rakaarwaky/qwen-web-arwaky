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

### Naming

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Orphan

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Scalability

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Data Flow

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

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
