# Operator runbook — Parsing failure (ErrorCategory: parsing)

**Alerts:** none specific; monitor `category=parsing`.
**Doctor:** no dedicated check.
**Severity:** warning — response text is empty or malformed.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `OutputValidationError`, category=parsing |
| Sentry | category=parsing accumulates |

## Recovery steps

1. Check whether the response contains a challenge page (Cloudflare / rate-limit).
   Those messages surface as `OutputValidationError` and should also trigger
   `rate_limit` categorization.
2. Retry with a longer response window:
   ```bash
   export QWEN_STREAM_SAFETY_TIMEOUT_SEC=3600
   ```
3. Verify the DOM selectors for `RESPONSE_CONTENT_SELECTOR`.

## Prevention

- Regressions in the response extractor are caught by the pinned DOM selector
  tests; ensure they pass before release.
