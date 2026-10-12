# Operator runbook — Disk exhaustion (ErrorCategory: file_io, subset: OSError/IOError with disk-full signals)

**Alerts:** `disk-pressure` (Sentry category=file_io, threshold 3 in 10m, severity critical)
**Doctor:** "Output Storage Permission" check fails when the output directory cannot be written.
**Severity:** critical — output cannot be persisted; jobs abort.

## Detection signals

| Source | Signal |
| --- | --- |
| Log | `file_io` category events, OSError/IOError with errno=EFDQUOTA/ENOSPC |
| Doctor | Output Storage Permission fails |
| Sentry | `disk-pressure` fires |
| System | dmesg or df reports disk full |

## Recovery steps

1. Run the doctor to confirm which XDG path is blocked:
   ```bash
   qwen-web-arwaky doctor
   ```
2. Check disk usage on the XDG base directories:
   ```bash
   df -h ~/.local/share/qwen-web-arwaky ~/.local/state/qwen-web-arwaky ~/.cache/ms-playwright
   du -sh ~/.local/state/qwen-web-arwaky/log/*
   ```
3. Prune recoverable waste:
   - Rotated app logs: `~/.local/state/qwen-web-arwaky/log/app.jsonl.{1..5}`
   - Per-run job logs: `~/.local/state/qwen-web-arwaky/jobs/*.jsonl`
   - Old snapshot backups beyond the configured retention: `~/.local/share/qwen-web-arwaky/qwen_session/.backups/`
4. After pruning, re-run `qwen-web-arwaky doctor` to confirm the output check passes.
5. Retry the job.

## Escalation

If the disk is on a shared partition and the host fills frequently, add cgroup memory+disk
limits (see deploy/qwen-web-arwaky.service MemoryMax/TasksMax) and set up a cron job to
rotate logs and notify the operator before reaching 80% capacity.

## Prevention

- The log handler uses `RotatingFileHandler(maxBytes=10MB, backupCount=5)`, which caps a
  single app.log at 50 MB. Larger workloads need `qwen-web-arwaky doctor` monitoring.
- Swarm workloads should be configured with `QWEN_WEB_MAX_WORKERS` derived from host memory
  (issue #291) so they do not overconsume disk via per-run snapshots.
