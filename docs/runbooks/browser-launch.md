# Operator runbook — Browser launch failure (ErrorCategory: browser)

**Alerts:** `browser-launch-failure` (Sentry threshold 3 in 5m, severity critical)
**Doctor:** "Playwright Chromium Browser" and "Browser Sandbox" checks.
**Severity:** critical — all runs fail with `BrowserLaunchError`.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `BrowserLaunchError` exception |
| Doctor | Playwright check fails or sandbox warning |
| Sentry | `browser-launch-failure` fires |
| Process | Orphaned Chromium processes on the host |

## Recovery steps

1. Check the doctor report:
   ```bash
   qwen-web-arwaky doctor
   ```
   Note the "Playwright Chromium Browser" and "Browser Sandbox" lines.
2. If Chromium is missing from the cache, reinstall it:
   ```bash
   python -m playwright install chromium
   ```
3. If the sandbox is dropped (`--no-sandbox`) because the host lacks seccomp or user
   namespaces, the process may still start but runs without OS isolation (see `qwen-web-arwaky doctor` output). In a production environment this is a WARNING — consider running under a container that grants user namespaces, or pass `QWEN_DISABLE_SANDBOX=0` and verify the host supports it.
4. Kill any orphaned Chromium processes:
   ```bash
   pkill -f "chromium.*no-sandbox" || true
   ```
5. Verify the session profile is intact (see runbooks/session-corruption.md).
6. Retry the job.

## Escalation

If Chromium starts but pages crash, check Playwright version pinning (see ISSUE.md) and
the CI/CD runner's memory pressure (issue #291).

## Prevention

- Monitor `doctor --json` for the sandbox check.
- Keep the Playwright cache healthy; run `sync-browser` as part of the release pipeline.
