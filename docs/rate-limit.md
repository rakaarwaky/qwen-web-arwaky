# Operator runbook — Rate limiting (ErrorCategory: rate_limit)

**Alerts:** `rate-limit-warning` (Sentry threshold 10 in 15m, severity warning)
**Doctor:** no dedicated check; doctor reports host capacity (issue #291).
**Severity:** warning — runs are retried, but throughput drops.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `RateLimitError` exception, category=rate_limit |
| Doctor | Host capacity line |
| Sentry | `rate-limit-warning` fires |

## Recovery steps

1. Reduce parallelism immediately:
   ```bash
   export QWEN_WEB_MAX_WORKERS=2
   export QWEN_SWARM_CONCURRENCY=2
   ```
2. Back off the schedule; let the queued jobs drain.
3. Investigate whether the rate limit is host-bound (per-cookie) or account-bound
   (per-user). The latter requires reducing concurrency across all profiles.
4. Resume normal concurrency once the counter clears.

## Prevention

- Set `QWEN_SWARM_CONCURRENCY` below the default 10 when the account is shared.
- Monitor `qwen-web-arwaky doctor --json` host capacity line; keep concurrent workers
  under the budgeted count.
