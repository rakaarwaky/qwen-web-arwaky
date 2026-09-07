"""Taxonomy: DevOps/SRE role prompt template constant.

Domain taxonomy constant layer for the built-in DevOps/SRE prompt template.
Operational concerns: deployment, observability, reliability, security hardening.
"""

from __future__ import annotations

EMBEDDED_DEVOPS_TEMPLATE: str = r"""# Plan: {feature} — DevOps / SRE

## Summary

{One paragraph describing the operational review scope: deployment target, observability stack, reliability requirements.}

## Findings

### Deployment & Packaging
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Entry point correctness, dependency pinning, build reproducibility, artifact size, version bump, CLI/MCP binary packaging -->

### Observability
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Sentry DSN configuration, OTel span coverage, structlog context propagation, log level configurability, error grouping, trace context propagation across async boundaries -->

### Reliability & Resilience
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Retry policy (tenacity), timeout defaults, graceful shutdown, signal handling, browser crash recovery, session expiry detection, idempotent operations -->

### Security Hardening
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Secrets in env vs config, cookie/session storage path permissions, dependency CVEs (pip-audit), Bandit findings, CORS/auth boundaries, prompt injection defense -->

### Configuration & Environment
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: XDG compliance, default path resolution, env var override support, config validation, missing-required-config error messages, backward-compatible config migration -->

### Release & CI
| # | Severity | Issue | Location | Recommendation |
| --- | ---------- | ------- | ---------- | ---------------- |
<!-- Check: Lint gate , test gate , type gate, security gate , version bump automation, changelog generation, branch protection -->

## Runbook

{Outline operational procedures: how to deploy, rollback, monitor, and respond to incidents.}

## Action Items

- [ ]  {Priority} {Item}

## Fixed Code

{Grouped by file}

## Severity

| Level | Meaning |
| ------- | ------------------------------------------------------------------------------ |
| 🔴 CRITICAL | Outage risk, security vuln, data leak, observability blind spot. Immediate fix. |
| 🟡 WARNING | Resilience gap, config fragility, CI gap, missing instrumentation. Fix this cycle. |
| 🟢 INFO | Hardening suggestion, cost optimization, DX improvement. Deferrable. |
"""

__all__ = ["EMBEDDED_DEVOPS_TEMPLATE"]
