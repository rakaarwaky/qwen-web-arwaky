"""Taxonomy: UI/UX role prompt template constant.

Domain taxonomy constant layer for the built-in UI/UX prompt template.
Consumer-oriented: every dimension maps to end-user experience impact
across any interactive surface (GUI, web, TUI, CLI, mobile, etc.).
"""

from __future__ import annotations

EMBEDDED_UI_UX_TEMPLATE: str = r"""# Plan: {feature} — UI/UX

## Summary

{One paragraph describing the interface context, user flow impacted, and scope of the review.}

## Findings

### Accessibility & Usability

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Input methods, keyboard/voice/screen-reader support, color contrast (WCAG 2.1 AA), focus management, semantic structure, discoverability -->

### Layout & Responsiveness

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Multi-size adaptation, overflow handling, density/breathing room, input target sizing, orientation changes -->

### UX Patterns & User Flow

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Loading/empty/error states, optimistic updates, undo capability, confirmation dialogs, platform conventions -->

### Component / Module Quality

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Reusability, interface clarity, composition over inheritance, controlled state, caching/memoization -->

### Visual Consistency & Design Tokens

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Design system adherence, spacing scale, color palette, typography scale, iconography, motion/animation -->

### Performance

| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | --------- | ---------------- |
<!-- Check: Startup time, render latency, memory footprint, input responsiveness, resource efficiency -->

## Violations

{List or "None"}

## User Flow Diagram

{Describe or diagram the affected user flow}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by component/file}

## Severity

| Level | Meaning |
| ------- | --------------------------------------------------------------------------------------- |
| CRITICAL | A11y/usability blocker, broken user flow, data loss risk, render crash. Immediate fix. |
| WARNING | UX friction, missing state, performance regression, inconsistent design. Fix this cycle. |
| INFO | Polish, micro-interaction, nice-to-have. Deferrable. |
"""

__all__ = ["EMBEDDED_UI_UX_TEMPLATE"]
