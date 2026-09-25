# Operator runbook — Network failure (ErrorCategory: network)

**Alerts:** `network-failures` (Sentry category=network, threshold 5 in 10m, severity warning)
**Doctor:** no dedicated check; check host connectivity.
**Severity:** warning — dispatches fail with DNS/connection errors.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `NetworkTimeoutError`, category=network |
| Sentry | `network-failures` fires |

## Recovery steps

1. Verify connectivity to `chat.qwen.ai`:
   ```bash
   curl -I https://chat.qwen.ai
   ```
2. Check whether a proxy or VPN is interfering; unset `http_proxy` / `https_proxy`
   if the runner does not route through them.
3. Retry.

## Prevention

- The job executor retries with exponential backoff for transient network errors.
- If failures persist across hosts, the upstream service is degraded; wait and
  requeue.
