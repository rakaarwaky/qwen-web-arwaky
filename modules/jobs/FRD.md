# JOBS Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The jobs feature runs long prompts outside the caller's request window and
keeps the state a poller needs. It owns the bounded worker pool, the
persistent job records, the per-run status file, and the stale-job
reconciliation that recovers a pool after a crash. The MCP and interactive
surfaces submit a job and read its record; they never own a worker.

## Functional Requirements

### FR-JOBS-001: Run a background job and keep its record recoverable

- **Description**: Queue a file or attachment prompt on the bounded worker pool, answer a poll for it, and keep every job record durable enough to survive a lost handle or a killed worker.
- **Input**: A job request naming the verb — submit, poll, list, or shut down — the prompt path, the optional attachment, the output path, the headless flag, a job identifier or listing limit, and the storage's own retention windows.
- **Output**: The persisted job record with its completed flag, result preview, and error; or the ordered list of records; or the count of records removed by cleanup.
- **Business Rules**:
  - Submission returns immediately; the caller polls for the result.
  - A pool that is already at its pending-job ceiling rejects the submission rather than queueing without bound.
  - Submission throttles to the configured per-minute rate; a throttled submit is reported as retryable with a wait hint.
  - A record that has not completed reports the running state regardless of any partial result.
  - Listing is the recovery path for a lost identifier and is ordered newest first.
  - A record whose worker died is reconciled to a terminal state on the next pool start, so a poller never waits on a job that will never finish.
  - A record is a zombie when its `owner_pid` no longer answers **or** its `heartbeat_at` is older than the heartbeat lease window (`JOB_HEARTBEAT_LEASE_SEC`); a recycled PID that answers `os.kill` is still a zombie when its heartbeat has gone stale.
  - A running job refreshes `heartbeat_at` at least once per half lease window, so a live worker is never reconciled; the refresh stops before the terminal save so it cannot resurrect a completed record.
  - Retention removes completed records past their terminal window and incomplete records past their longer window.
- **Edge Cases**:
  - A repeated failure trips the circuit breaker and later submissions fail fast with the breaker's reason until its window elapses.
  - An unknown or expired identifier reports a not-found error rather than an empty record.
  - A storage directory that does not exist is created rather than reported as missing.
- **Error Handling**:
  - Queue-full, throttled, and breaker-open outcomes each carry their own error category so the caller can decide whether to retry. The queue-full outcome reaches MCP and CLI surfaces as its own envelope (MCP `QUEUE_FULL`, CLI `cli-429`) preserving `retry_after_sec` and `queue_depth`.
  - Not-found carries the hint that listing recovers the identifier.
  - A record that cannot be written surfaces a file error naming the path; the job still runs.

### FR-JOBS-002: Publish and read the per-run status file

- **Description**: Write the status file an external monitor reads while a run is in flight, and read a published file back.
- **Input**: The run's status record, or the published status file to read.
- **Output**: The written status file, or the parsed mapping when read back.
- **Business Rules**:
  - The status file is the inter-process handoff: its field set is what an external monitor depends on, so removing a field is a breaking change. The schema-version-2 key set is pinned by a contract test in the shared member's test suite.
  - An absent, empty, or invalid status file reads back as no mapping rather than raising.
- **Edge Cases**: A status file that has not been written yet reads back as no mapping.
- **Error Handling**: A status write that fails surfaces a file error naming the path.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `save_job` | job record | saved record | file error | none | Persist a job record durably. |
| `get_job` | job identifier | job record | not-found error | none | Read one persisted record. |
| `list_jobs` | listing limit | ordered job records | none | none | List records newest first. |
| `cleanup_stale_jobs` | retention windows | removed count | file error | none | Remove records past their retention window. |
| `reconcile_zombies` | worker state | reconciled record count | none | none | Move records whose worker died to a terminal state. |
| `write` | status record | status file path | file error | none | Publish the run's status file. |
| `write_record` | status record | status file path | file error | none | Publish a status record variant. |
| `read` | none; reads the published status file | parsed status mapping or none | none | none | Read a published status file back. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | job request naming the verb | job response carrying the record, records, or removed count | queue-full, throttled, breaker-open, not-found, file error | dispatch acknowledged, generation finished, failed | Single entry point callers use to submit, poll, list, or shut the pool down. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| MCP surface | in | Submit async prompt tools and poll results | queue-full or throttled -> structured retryable envelope |
| Interactive slots | in | Run a slot's prompt without blocking the UI | throttled -> slot reports backpressure |
| Swarm orchestrators | in | Fan out prompts through the same bounded pool | queue-full -> fan-out leg fails |
| External monitors | out | Read the published status file | absent file -> no mapping, not an error |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Submission latency | returns without waiting for the prompt result | timing the submit verb |
| Pending-job ceiling | enforced per worker; submission rejected at the ceiling | queue-depth check at submit |
| Zombie reconciliation | every record whose worker died reaches a terminal state before the first poll after restart | reconciliation count against injected zombie records |

## Test Scenarios

- A submitted job returns a persisted record immediately and later reports completion.
- A pool at its pending-job ceiling rejects a submission with the queue-full category.
- A record whose worker was killed is reconciled to a terminal state on the next pool start.
- A listing recovers the identifier of a job whose handle the caller lost.
- An absent status file reads back as no mapping rather than raising.

## Assumptions & Constraints

- Job records outlive the process that created them; a poller may return after the submitting run ends.
- The published status file's field set is a compatibility surface for external monitors.

## Glossary

- **Job record**: The persisted state of one queued prompt: identifier, verb, paths, status, timestamps, worker ownership.
- **Zombie record**: A record whose worker process died before completing the job.
- **Pending-job ceiling**: The per-worker bound on jobs queued but not yet started.
