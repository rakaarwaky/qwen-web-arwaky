# BA decisions and business rules

Approved 2026-09-22 for BA issues #272-#286.

## Scope

The product is in **Stabilization + Targeted Enhancement Mode**. Swarm
orchestration, asynchronous job management, and self-update are approved
in-scope enhancements under change request `CR-2026-004`.

## Reliability

A pipeline execution is one prompt file dispatched to a terminal success or
explicit error envelope. The success rate is calculated over a rolling 24-hour
window from persisted `metrics.json` counters. Warning is below 99.5%; critical
is below 99.0%.

## Model ownership

`Qwen3.8-Max` remains the only supported/default model. Model changes are a
maintainer responsibility and are updated in a versioned release; no end-user
model selector or override is required.

## Operational limits

- Maximum concurrent browser workers: 10, configurable by maintainer/operator.
- MCP job records expire after 24 hours after terminal completion and stale
  incomplete records are retained for 7 days for diagnosis before cleanup.
- Attachments over 100 MB are rejected before browser interaction with a clear
  validation error.
- A session expiry during a long-running operation is a terminal, retryable
  failure with instruction to authenticate again; partial outputs remain safe.
