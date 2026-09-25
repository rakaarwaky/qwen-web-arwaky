# Operator runbook — Injection failure (ErrorCategory: injection)

**Alerts:** none specific; monitor `category=injection` on sentry.
**Doctor:** no dedicated check.
**Severity:** warning — prompt text cannot reach the chat input.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `PromptInjectionError`, category=injection |
| Sentry | category=injection accumulates |

## Recovery steps

1. Verify the DOM selectors still match the live page; check
   `modules/core/src/utility_core_dom_query.py` for recent commits.
2. Re-run with `--verbose` to see the injection strategy transcript.
3. Retry.

## Prevention

- Pin the DOM helpers after every QA release; regressions in qwen-chat UI surface
  as this error category.
