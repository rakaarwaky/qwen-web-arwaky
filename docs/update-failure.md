# Operator runbook — Update failure (ErrorCategory: update)

**Alerts:** `update-failure` (Sentry category=update, threshold 1 in 24h, severity warning)
**Doctor:** no dedicated check; the update pipeline runs `run_doctor_checks(include_heavy=True)`
as a post-flight gate (issue #294).
**Severity:** warning — the host reverts to the previous version automatically if a rollback
succeeds. A silent failure leaves the host on the broken release.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `package_upgrade_failed`, `rollback` step failures |
| Doctor | Postflight health checks (Python, package metadata, Chromium) |
| Sentry | `update-failure` fires |
| Status | `status.json` contains an `"error"` field after an upgrade attempt |

## Recovery steps

1. Check the last update report:
   ```bash
   qwen-web-arwaky update check
   ```
2. If a rollback occurred, the previous version is restored and the host is
   operational. Confirm the running version:
   ```bash
   qwen-web-arwaky --version
   ```
3. If the rollback also failed, revert manually to the last known-good version:
   ```bash
   pip install git+https://github.com/rakaarwaky/qwen-web-arwaky.git@<previous-sha>
   python -m playwright install chromium
   ```
   The previous SHA is recorded in the rollback snapshot under
   `~/.local/state/qwen-web-arwaky/state/prev_snapshot.txt` when available.
4. Do not retry the same release; instead open a bug against the latest tag.

## Escalation

If repeated updates fail on the same release, pin the release URL to the commit
SHA (issue #368) and check the changelog for breaking Playwright pins or dependency
changes. File a severity-warning issue under the DO bucket.

## Prevention

- The update pipeline installs the release pinned to an immutable commit SHA; a
  re-pointed tag cannot silently swap code.
- The postflight gate runs functional doctor checks (issue #294) so a release that
  breaks the real code path is caught before it reaches production.
