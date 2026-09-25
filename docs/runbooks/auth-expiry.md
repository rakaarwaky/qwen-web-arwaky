# Operator runbook — Auth expiry (ErrorCategory: auth)

**Alerts:** `session-expiry-critical` (Sentry threshold 2 in 10m, severity critical)
**Doctor:** "Session Authentication Token" check fails when the saved profile is missing or invalid.
**Severity:** critical — unattended jobs cannot authenticate with Qwen.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `AuthRequiredError` exception, category=auth |
| Doctor | Session check fails |
| Sentry | `session-expiry-critical` fires |
| Status | `status.json` contains `"error"` key |

## Recovery steps

1. Inspect the error category with `qwen-web-arwaky doctor --json` and check `status.json`.
2. Verify the session directory exists and is not empty:
   ```bash
   ls -la ~/.local/share/qwen-web-arwaky/qwen_session
   ```
3. Try to restore the newest snapshot (if one exists):
   ```bash
   qwen-web-arwaky session restore
   ```
   If no backup is retained, the only recovery is an interactive CAPTCHA re-login.
4. Re-authenticate interactively:
   ```bash
   qwen-web-arwaky login
   ```
   A headed browser opens at chat.qwen.ai; finish any CAPTCHA challenge. The resulting
   profile is backed up automatically on success.
5. After login, validate:
   ```bash
   qwen-web-arwaky doctor
   ```

## Escalation

If CAPTCHA blocks are repeated (likely rate-limited account), contact the Qwen platform
owner. Do not attempt programmatic CAPTCHA solving.

## Prevention

- Run `qwen-web-arwaky login` proactively before every long unattended batch.
- Keep a backup generation in place; doctor warns when none exist.
