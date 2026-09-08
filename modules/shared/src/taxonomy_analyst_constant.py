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
<!-- Check: Ambiguous wording, missing acceptance criteria, stakeholder alignment, requirement completeness, measurable outcomes -->

### Business Flow
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Happy path coverage, edge case handling, error/recovery flows, regulatory compliance, data ownership boundaries -->

### Logic Implementation
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Requirement-to-code mapping, conditional logic correctness, boundary conditions, business rule enforcement, negative paths -->

### Testability & Acceptance
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Test scenario coverage, acceptance criteria testability, mockability of external dependencies, reproducible test setup -->

### Traceability (FRD to Code)
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: FRD section to code mapping, requirement orphan detection, change impact coverage, documentation synchronization, audit trail -->

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
