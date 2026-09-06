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

### Performance

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Error Handling

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### SOLID

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Code Quality

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

### Maintainability

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level | Meaning |
| ------- | ------------------------------------------------------------------- |
| 🔴 CRITICAL | Security vuln, data leak, crash risk. Immediate fix. |
| 🟡 WARNING | Perf bottleneck, SOLID violation, bypass pattern. Fix this cycle. |
| 🟢 INFO | Nice-to-have. Deferrable. |
"""

__all__ = ["EMBEDDED_BACKEND_TEMPLATE"]
