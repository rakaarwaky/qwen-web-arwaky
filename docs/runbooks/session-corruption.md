# Operator runbook — Session corruption (ErrorCategory: session)

**Alerts:** `session-corruption` (Sentry category=session, threshold 1 in 60m, severity critical)
**Doctor:** "Session Authentication Token" check fails, with or without a backup warning.
**Severity:** critical — the master profile is unreadable or invalid.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `OSError` or `IOError` reading the session directory |
| Doctor | Session check fails; backup warning if present |
| Sentry | `session-corruption` fires |
| Process | Orphaned `SingletonLock` / `DevToolsActivePort` files in the master profile |

## Recovery steps

1. Confirm the corruption:
   ```bash
   qwen-web-arwaky doctor
   ls -la ~/.local/share/qwen-web-arwaky/qwen_session
   ls -la ~/.local/share/qwen-web-arwaky/qwen_session/.backups
   ```
2. If a backup exists, restore the newest generation:
   ```bash
   qwen-web-arwaky session restore
   ```
   This copies the backup back into `qwen_session` and validates the result.
3. If no backup is retained (see issue #300), the only recovery is an interactive
   re-login with CAPTCHA:
   ```bash
   rm -rf ~/.local/share/qwen-web-arwaky/qwen_session
   qwen-web-arwaky login
   ```
   A successful login takes an automatic backup.
4. After restore or re-login, run `qwen-web-arwaky doctor` to confirm both checks
   pass.

## Escalation

If `.backups` is empty and the session is corrupted, the loss is permanent until
the user completes the interactive login. Investigate whether `delete_session` was
called with `force=True` without a retained snapshot (issue #300).

## Prevention

- Every successful `setup_session` call automatically snapshots the master profile.
- `delete_session` refuses to proceed when no backup is retained unless `force=True`
  is explicitly passed.
- Keep `MAX_GENERATIONS` at its default of 3; doctor warns when the count falls to 0.
