# Operator runbook — Stuck run (ErrorCategory: stuck)

**Alerts:** `stuck-runs` (Sentry category=stuck, threshold 3 in 15m, severity warning)
**Doctor:** no dedicated check; check `status.json` for stuck runs.
**Severity:** warning — runs hold browser contexts without progress.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `StuckDetectedError`, category=stuck |
| Sentry | `stuck-runs` fires |

## Recovery steps

1. Cancel the stuck run via the CLI or the cancel registry:
   ```bash
   qwen-web-arwaky --cancel <run_id>
   ```
2. If the browser context is unrecoverable, kill any orphaned Chromium processes:
   ```bash
   pkill -f "chromium.*no-sandbox" || true
   ```
3. Verify the session profile locks are clean (singletons are auto-pruned on clone).
4. Retry.

## Prevention

- `QWEN_STREAM_SAFETY_TIMEOUT_SEC` controls the stall detection; raise it if slow
  models legitimately take longer than the default.
- The circuit breaker (`circuit_breaker_threshold`, `circuit_breaker_window`) trips
  when consecutive failures hit the threshold — use it to stop cascading stuck runs.
