# LOGGING Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The logging feature bootstraps observability for one run: it attaches the
structured log handlers, stamps the run's identity into every record,
records metrics for the counters a quality report reads, writes the
inter-process status file, and closes the run cleanly. Both entry runtimes
call one orchestrator verb, so the argument contract lives in one place.

## Functional Requirements

### FR-LOGGING-001: Bootstrap observability for one run

- **Description**: Attach the log handlers and exception hooks a run needs.
- **Input**: An observability request naming the verb, the log path, the run id, and whether a standard-error handler may be attached.
- **Output**: An observability response naming the attached handlers and the run stamp.
- **Business Rules**:
  - An entry that owns the terminal canvas must attach no standard-error handler, so run records cannot corrupt the interactive UI.
  - Every record emitted from a worker thread routes through the same run stamp, so a record names the run that produced it.
- **Edge Cases**: A bootstrap run twice with the same run id attaches no duplicate handler.
- **Error Handling**: A log path the host cannot write to surfaces a file error naming the path.

### FR-LOGGING-002: Record metrics for a quality report

- **Description**: Count the outcomes a run produced so a report can read them back.
- **Input**: The execution or failure outcome to record.
- **Output**: The counter snapshot after recording.
- **Business Rules**:
  - A failure records both its outcome and its category, so a report separates retried faults from terminal ones.
  - A snapshot is a read that does not mutate the counters.
- **Edge Cases**: A snapshot taken before any run records an all-zero report.
- **Error Handling**: A counter that cannot be read back reports the absence rather than raising.

### FR-LOGGING-003: Publish the run status and quality report

- **Description**: Write the inter-process status file and the run's quality report.
- **Input**: The status record, or the run's final metrics.
- **Output**: The written status path, or the quality-report path.
- **Business Rules**:
  - The status file is the inter-process handoff; its field set is what an external monitor depends on.
  - The quality report is written at run end, not during the run.
- **Edge Cases**: A status file the host cannot write to surfaces a file error naming the path; the run still completes.
- **Error Handling**: A quality-report write that fails surfaces a file error; the run's outcome is not affected.

### FR-LOGGING-004: Close a run

- **Description**: Detach the run's log handler and report its exit code.
- **Input**: The run's outcome code.
- **Output**: The exit code, with the run's records flushed.
- **Business Rules**:
  - Detaching flushes the run's records before the process exits, so a crash cannot lose its final records.
  - The exit code a run reports is decided by one rule shared with the surfaces that print it.
- **Edge Cases**: A close run called twice detaches only once; the second call is a no-op.
- **Error Handling**: A flush that fails surfaces the underlying error; the exit code still names the outcome.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `setup_observability` | observability request | observability response | file error | none | Attach the handlers a run needs. |
| `bind_run_context` | run id | bound context | none | none | Stamp the run id into records. |
| `clear_run_context` | none | none | none | none | Clear the run stamp. |
| `attach_run_log` | log path | attached handler | file error | none | Attach the run's file handler. |
| `detach_run_log` | log path | flushed verdict | file error | none | Detach and flush the run's handler. |
| `exit_code_for` | outcome code | process exit code | none | none | Decide the exit code one shared rule. |
| `write_status` | status record | status path | file error | none | Publish the inter-process status file. |
| `write_quality_report` | run metrics | report path | file error | none | Write the run's quality report. |
| `install_excepthooks` | none | installed verdict | none | none | Install the run's exception hooks. |
| `start_span` | span name | active span | none | none | Open a metrics span. |
| `record_execution` | outcome | snapshot | none | none | Record one execution outcome. |
| `record_failure` | failure category | snapshot | none | none | Record one failure. |
| `increment` | counter name | new value | none | none | Increment one counter. |
| `get` | counter name | counter value | none | none | Read one counter without mutating it. |
| `failure_counts` | none | failure snapshot | none | none | Report the failure counters. |
| `snapshot` | none | metrics snapshot | none | none | Report every counter without mutating them. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | observability request naming the verb | observability response carrying the verb's outcome | file error | none | Single entry point both entry runtimes call to run any observability verb. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| CLI entry | in | Bootstrap and close every run | file error -> the run proceeds without the handler |
| MCP entry | in | Bootstrap and close every tool invocation | file error -> the run proceeds without the handler |
| External monitors | out | Read the published status file | absent file -> no mapping, not an error |
| Quality-report consumer | out | Read the run's outcome counts | absent report -> all-zero snapshot |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Interactive UI leak | zero run records written to the standard-error handler on the interactive path | stderr capture during a run with `attach_stderr` false |
| Flush completeness | every record emitted before close is written to disk | record count against the log file after close |
| Snapshot purity | a counter read never mutates the counter | snapshot-equality check around a read |

## Test Scenarios

- An interactive bootstrap attaches no standard-error handler and a later run record appears only in the log file.
- A bootstrap run twice with the same run id attaches no duplicate handler.
- A failure recorded with its category is separable from a retried fault in a quality report.
- A close run flushes the run's records before returning the exit code.
- A status write that fails surfaces a file error and the run still completes.

## Assumptions & Constraints

- The standard-error handler is the only channel that can corrupt the interactive terminal; every other handler is safe to attach on that path.
- The status file's field set is a compatibility surface for external monitors.

## Glossary

- **Run stamp**: The run id attached to every record the run emits.
- **Quality report**: The per-run outcome counts an operator reads after a run.
- **Inter-process status file**: The JSON handoff an external monitor polls while a run is in flight.
