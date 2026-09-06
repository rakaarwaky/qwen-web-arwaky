"""Taxonomy: frontend/UI-UX role prompt template constant.

Domain taxonomy constant layer for the built-in Frontend/UI-UX prompt template.
Consumer-oriented: every dimension maps to end-user experience impact.
"""

from __future__ import annotations

EMBEDDED_FRONTEND_TEMPLATE: str = r"""# Plan: {feature} — Frontend / UI-UX

## Summary

{One paragraph describing the UI/UX context, user flow impacted, and scope of the review.}

## Findings

### Accessibility (a11y)

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: ARIA labels, keyboard navigation, screen reader support, color contrast (WCAG 2.1 AA), focus management, semantic HTML -->

### Responsiveness & Layout

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Mobile-first, breakpoint consistency, overflow handling, viewport meta, touch targets (min 44x44px) -->

### UX Patterns & User Flow

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Loading states, empty states, error states, optimistic updates, undo capability, confirmation dialogs -->

### Component Quality

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Reusability, prop interface clarity, composition over inheritance, controlled vs uncontrolled, memoization -->

### Visual Consistency & Design Tokens

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Design system adherence, spacing scale, color palette, typography scale, icon usage, animations -->

### Performance (Client-Side)

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Bundle size, lazy loading, code splitting, image optimization, CLS, FCP/LCP/TBT, SSR/SSG hydration -->

## User Flow Diagram

{Describe or diagram the affected user flow}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by component/file}

## Severity

| Level | Meaning |
| ------- | --------------------------------------------------------------------------------------- |
| 🔴 CRITICAL | A11y blocker, broken user flow, data loss risk, render crash. Immediate fix. |
| 🟡 WARNING | UX friction, missing state, performance regression, inconsistent design. Fix this cycle. |
| 🟢 INFO | Polish, micro-interaction, nice-to-have. Deferrable. |
"""

__all__ = ["EMBEDDED_FRONTEND_TEMPLATE"]
