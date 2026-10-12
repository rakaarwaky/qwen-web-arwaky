# Operator runbook — Uncategorized error (ErrorCategory: other)

**Alerts:** `categorized-error-backlog` (Sentry category=other, threshold 5 in 15m, severity warning)
**Doctor:** no dedicated check.
**Severity:** warning — an error falls outside the known categories; classify it.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `category=other` logged with the full exception traceback |
| Sentry | `categorized-error-backlog` fires |

## Recovery steps

1. Read the full exception from the JSONL log:
   ```bash
   jq -r 'select(.category == "other")' ~/.local/state/qwen-web-arwaky/log/app.jsonl | tail -20
   ```
2. Triage the exception type:
   - If it matches an existing error class, move the incident to the corresponding
     runbook.
   - If it is new, add an exception subclass to `taxonomy_core_error.py`, a keyword
     rule to `ErrorCategory.categorize`, and a new runbook.
3. If it is an unresolvable transient (e.g., a one-off 5xx from the Qwen backend),
   log it as `other` with a human-readable note and proceed.

## Escalation

Repeated `other` errors without a matching exception class indicate incomplete
observability; file a severity-warning issue under the DO bucket to close the gap.

## Prevention

- Keep the taxonomy `ErrorCategory` table current with every new failure mode so
  future incidents are actionable on first alert.
