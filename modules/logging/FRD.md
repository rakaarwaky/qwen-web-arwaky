# LOGGING Functional Requirements Document

## Feature Overview

The logging feature bootstraps observability for one run: it attaches the
structured log handlers, stamps the run's identity into every record,
records metrics for the counters a quality report reads, writes the
inter-process status file, and closes the run cleanly. Both entry runtimes
call one orchestrator verb (`IObservabilityAggregate.execute`), so the
argument contract lives in one place.

## Functional Requirements

### FR-LOGGING-001: Carry one run through its observability lifecycle

**Description:**

Attach the handlers a run needs, stamp the run into its records, publish
what an external monitor reads, and close the run.

#### Business Logic

- An entry that owns the terminal canvas must attach no standard-error handler, so run records cannot corrupt the interactive UI.
- Every record emitted from a worker thread routes through the same run stamp, so a record names the run that produced it.
- The status file is the inter-process handoff; its field set is what an external monitor depends on, pinned for schema version 2 by a contract test in the shared member's test suite.
- The quality report is written at run end, not during the run.
- Detaching flushes the run's records before the process exits, so a crash cannot lose its final records.
- The exit code a run reports is decided by one rule shared with the surfaces that print it.

#### Edge Cases

- A bootstrap run twice with the same run id attaches no duplicate handler.
- A close run called twice detaches only once; the second call is a no-op.
- A status file the host cannot write to surfaces a file error naming the path; the run still completes.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | An observability request naming the verb — bootstrap, publish, or close — the log path, the run id, whether a standard-error handler may be attached, and the status fields or final metrics a publish carries. |
| **Output** | The attached handlers and the run stamp, the written status path or quality-report path, and the exit code with the run's records flushed. |
| **Protocol** | `IObservabilityProtocol` — the run-observability bootstrap and close seam. |
| **Method** | `setup_observability`, `bind_run_context`, `clear_run_context`, `attach_run_log`, `detach_run_log`, `exit_code_for`, `write_status`, `write_quality_report`, `install_excepthooks`. |
| **Event** | `run_closed` — emitted when the run's handlers are detached and flushed. |
| **Error** | A log path the host cannot write to surfaces a file error naming the path; a quality-report write that fails surfaces a file error and the run's outcome is not affected; a flush that fails surfaces the underlying error, but the exit code still names the outcome. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An interactive bootstrap | A run record is emitted | It appears only in the log file, never the standard-error handler |
| A bootstrap run twice with the same run id | The handlers attach | No duplicate handler is created |
| A close run | Detachment runs | The run's records are flushed before the exit code returns |

#### Metric

| Target Metric | Value |
| --- | --- |
| Interactive UI leak | Zero run records written to the standard-error handler on the interactive path |

### FR-LOGGING-002: Record metrics for a quality report

**Description:**

Count the outcomes a run produced so a report can read them back.

#### Business Logic

- A failure records both its outcome and its category, so a report separates retried faults from terminal ones.
- A snapshot is a read that does not mutate the counters.

#### Edge Cases

- A snapshot taken before any run records an all-zero report; a counter that cannot be read back reports the absence rather than raising.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The execution or failure outcome to record; or a counter name for a single read. |
| **Output** | The counter snapshot after recording. |
| **Protocol** | `IMetricsProtocol` — the per-run counter recording and snapshot seam. |
| **Method** | `start_span`, `record_execution`, `record_failure`, `increment`, `get`, `failure_counts`, `snapshot`. |
| **Event** | None — the counter snapshot is the observable result. |
| **Error** | A counter that cannot be read back reports the absence rather than raising. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A failure recorded with its category | A quality report is read back | The fault is separable from a retried fault |
| A counter read around a snapshot | `get` runs | The read never mutates the counter |

#### Metric

| Target Metric | Value |
| --- | --- |
| Snapshot purity | A counter read never mutates the counter |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `LoggingOrchestrator` |
| Aggregate | `IObservabilityAggregate` |
| Method | `execute` |
| Request | `ObservabilityRequest` — verbs bootstrap, publish, close |
| Response | `ObservabilityResponse` — carries the attached handlers, the written path, and the exit code |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
