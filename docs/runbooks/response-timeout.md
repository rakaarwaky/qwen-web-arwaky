# Operator runbook — Response timeout (ErrorCategory: response_timeout)

**Alerts:** `response-timeouts` (Sentry category=response_timeout, threshold 3 in 15m, severity warning)
**Doctor:** "Playwright Chromium Browser" probe (with `QWEN_DOCTOR_DEEP=1`).
**Severity:** warning — runs complete but return nothing.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `ResponseDetectionTimeoutError`, category=response_timeout |
| Doctor | None directly; look for network errors first |
| Sentry | `response-timeouts` fires |

## Recovery steps

1. Check whether the Qwen service is degraded: open `https://chat.qwen.ai` in a browser.
2. Increase the streaming safety timeout for slow models:
   ```bash
   export QWEN_STREAM_SAFETY_TIMEOUT_SEC=7200
   ```
3. Verify the DOM selectors have not drifted; check `ISSUE.md` for known selector changes.
4. Retry the job.

## Prevention

- Pin the Playwright version in `uv.lock`; a newer driver may introduce different
  headless behaviours.
- Monitor the DOM helpers; if selectors drift across a release, file a severity-warning
  issue.
