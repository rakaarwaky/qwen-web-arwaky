# JOBS Functional Requirements Document

## Feature Overview

The jobs feature runs long prompts outside the caller's request window and
keeps the state a poller needs. It owns the bounded worker pool, the
persistent job records, the per-run status file, and the stale-job
reconciliation that recovers a pool after a crash. The MCP and interactive
surfaces submit a job and read its record; they never own a worker. The
orchestrator routes verbs to `IJobManagerAggregate.execute`, backed by the
job-storage and status-file capabilities.

## Functional Requirements

### FR-JOBS-001: Run a background job and keep its record recoverable

**Description:**

Queue a file or attachment prompt on the bounded worker pool, answer a poll
for it, and keep every job record durable enough to survive a lost handle or
a killed worker.

#### Business Logic

- Submission returns immediately; the caller polls for the result.
- A pool that is already at its pending-job ceiling rejects the submission rather than queueing without bound.
- Submission throttles to the configured per-minute rate; a throttled submit is reported as retryable with a wait hint.
- A record that has not completed reports the running state regardless of any partial result.
- Listing is the recovery path for a lost identifier and is ordered newest first.
- A record whose worker died is reconciled to a terminal state on the next pool start, so a poller never waits on a job that will never finish.
- A record is a zombie when its `owner_pid` no longer answers **or** its `heartbeat_at` is older than the heartbeat lease window (`JOB_HEARTBEAT_LEASE_SEC`); a recycled PID that answers `os.kill` is still a zombie when its heartbeat has gone stale.
- A running job refreshes `heartbeat_at` at least once per half lease window, so a live worker is never reconciled; the refresh stops before the terminal save so it cannot resurrect a completed record.
- Retention removes completed records past their terminal window and incomplete records past their longer window.

#### Edge Cases

- A repeated failure trips the circuit breaker and later submissions fail fast with the breaker's reason until its window elapses.
- An unknown or expired identifier reports a not-found error rather than an empty record.
- A storage directory that does not exist is created rather than reported as missing.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A job request naming the verb — submit, poll, list, or shut down — the prompt path, the optional attachment, the output path, the headless flag, a job identifier or listing limit, and the storage's own retention windows. |
| **Output** | The persisted job record with its completed flag, result preview, and error; or the ordered list of records; or the count of records removed by cleanup. |
| **Protocol** | `IJobManagerAggregate` — the single aggregate door over the job feature. |
| **Method** | `execute` routes the verb; `save_job`, `get_job`, `list_jobs`, `cleanup_stale_jobs`, `reconcile_zombies` are the storage capability methods. |
| **Event** | `dispatch_acknowledged`, `generation_finished`, `failed` — emitted by the worker as the job advances. |
| **Error** | Queue-full, throttled, and breaker-open outcomes each carry their own error category so the caller can decide whether to retry. The queue-full outcome reaches MCP and CLI surfaces as its own envelope (MCP `QUEUE_FULL`, CLI `cli-429`) preserving `retry_after_sec` and `queue_depth`. Not-found carries the hint that listing recovers the identifier. A record that cannot be written surfaces a file error naming the path; the job still runs. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A submitted job | The pool accepts it | A persisted record returns immediately and later reports completion |
| A pool at its pending-job ceiling | A submission arrives | The queue-full category is returned with a retry hint |
| A record whose worker was killed | The next pool start runs | The record is reconciled to a terminal state |

#### Metric

| Target Metric | Value |
| --- | --- |
| Zombie reconciliation | Every record whose worker died reaches a terminal state before the first poll after restart |

### FR-JOBS-002: Publish and read the per-run status file

**Description:**

Write the status file an external monitor reads while a run is in flight,
and read a published file back.

#### Business Logic

- The status file is the inter-process handoff: its field set is what an external monitor depends on, so removing a field is a breaking change. The schema-version-2 key set is pinned by a contract test in the shared member's test suite.
- An absent, empty, or invalid status file reads back as no mapping rather than raising.

#### Edge Cases

- A status file that has not been written yet reads back as no mapping.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The run's status record, or the published status file to read. |
| **Output** | The written status file, or the parsed mapping when read back. |
| **Protocol** | `IJobStorageProtocol` — the status-file publish and read seam. |
| **Method** | `write`, `write_record`, `read`. |
| **Event** | None — the published mapping is the observable result. |
| **Error** | A status write that fails surfaces a file error naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An absent status file | `read` runs | It returns no mapping rather than raising |
| A valid status file | `read` runs | The parsed mapping is returned |

#### Metric

| Target Metric | Value |
| --- | --- |
| Status-file schema-version-2 key-set stability | Pinned by a shared contract test |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `JobOrchestrator` |
| Aggregate | `IJobManagerAggregate` |
| Method | `execute` |
| Request | `JobRequest` — verbs submit, poll, list, and shut down |
| Response | `JobResponse` — carries the persisted record, the ordered record list, or the removed count |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
