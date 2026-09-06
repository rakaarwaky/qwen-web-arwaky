"""Taxonomy: business analyst role prompt template constant.

Domain taxonomy constant layer for the built-in Business Analyst prompt template.
"""

from __future__ import annotations

EMBEDDED_ANALYST_TEMPLATE: str = r"""# Plan: {feature} — Business Analyst

## Summary

{One paragraph describing the business analysis scope.}

## Findings

### Requirements Clarity

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Business Flow

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Logic Implementation

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Testability & Acceptance

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Traceability (FRD to Code)

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
| ------- | ------------------------------------------------------------------------------------------ |
| 🔴 CRITICAL | Missing core requirement, wrong logic, data integrity risk. Immediate fix. |
| 🟡 WARNING | Ambiguous requirement, missing edge case, incomplete criteria. Fix this cycle. |
| 🟢 INFO | Suggestion or optimization. Deferrable. |
"""

__all__ = ["EMBEDDED_ANALYST_TEMPLATE"]
