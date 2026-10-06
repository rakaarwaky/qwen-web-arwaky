# SWARM Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The swarm feature fans one prompt out across several browser sessions and
runs them concurrently. It owns the fan-out runner, the progress snapshot
a caller polls, and the cancellation path. Callers start a fan-out, read a
snapshot while it runs, and cancel it; they never own a browser or a thread.

## Functional Requirements

### FR-SWARM-001: Start a fan-out

- **Description**: Run one prompt across the requested number of browsers concurrently.
- **Input**: A swarm request naming the verb, the prompt source, the browser count, and the run configuration.
- **Output**: A swarm response carrying the fan-out handle, or the reason it could not start.
- **Business Rules**:
  - The fan-out never exceeds the host's concurrency ceiling; a request above it is clamped and the clamp is reported.
  - Each leg runs against its own session, so one leg's rate limit does not stop the others.
  - Legs are bounded by a per-leg retry budget; a leg that exhausts it fails while the rest continue.
- **Edge Cases**: A browser count below one is clamped to one rather than producing an empty fan-out.
- **Error Handling**: A leg that fails records its own error in the snapshot; the fan-out as a whole reports completed with per-leg verdicts.

### FR-SWARM-002: Report fan-out progress

- **Description**: Report the current state of a running fan-out.
- **Input**: The fan-out handle.
- **Output**: A snapshot naming each leg's status, its session, and its response path.
- **Business Rules**:
  - A snapshot is a read that never mutates the fan-out.
  - A leg that has not started yet reports pending rather than absent.
- **Edge Cases**: A snapshot of a fan-out that never started reports no legs.
- **Error Handling**: A snapshot whose handle is unknown reports no legs rather than raising.

### FR-SWARM-003: Cancel a fan-out

- **Description**: Stop every leg of a running fan-out.
- **Input**: The fan-out handle.
- **Output**: The number of legs stopped.
- **Business Rules**: A leg that already reached a terminal state is not reported as stopped.
  - Cancellation does not roll back legs that already wrote their response file.
- **Edge Cases**: A cancel on a completed fan-out reports zero.
- **Error Handling**: A cancel whose handle is unknown reports zero rather than raising.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `start` | swarm request naming the verb | swarm response carrying the handle | fan-out error | dispatch acknowledged | Start one fan-out. |
| `snapshot` | fan-out handle | swarm snapshot | none | none | Report per-leg progress. |
| `cancel` | fan-out handle | stopped-leg count | none | none | Stop every running leg. |
| `browser_concurrency` | run configuration | fan-out ceiling | none | none | Report how many fan-out browsers may run at once. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | swarm request naming the verb | swarm response carrying the handle, the snapshot, or the stopped-leg count | fan-out error | dispatch acknowledged, generation finished, failed | Single entry point callers use to start, inspect, or cancel a fan-out. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Surfaces | in | Start a fan-out and watch its progress | fan-out error -> surface reports the clamp or the failure |
| Session feature | out | Obtain one healthy session per leg | no-healthy-session -> that leg fails |
| Job manager | out | Run long fan-out legs outside the caller window | queue-full -> the caller clamps the browser count |
| External monitors | out | Read the snapshot while a fan-out runs | unknown handle -> no legs |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Concurrency clamp | a request above the ceiling never opens more browsers than the ceiling | open-browser count against the ceiling |
| Snapshot purity | a snapshot never mutates the fan-out | snapshot-equality check around a read |
| Cancel completeness | every running leg stops | stopped-leg count against the running-leg count |

## Test Scenarios

- A fan-out above the host ceiling clamps and reports the clamp.
- A leg that fails records its own error while the other legs complete.
- A snapshot of a leg that has not started reports it pending.
- A cancel on a completed fan-out reports zero stopped legs.
- A cancel stops every running leg and leaves written response files in place.

## Assumptions & Constraints

- Fan-out concurrency is bounded by the host's capacity ceiling and by the session pool's healthy count.
- One prompt source is fanned out; per-leg prompt variation stays out of scope.

## Glossary

- **Leg**: One browser's execution of the fanned-out prompt.
- **Snapshot**: The per-leg progress record a caller polls.
- **Concurrency ceiling**: The highest number of fan-out browsers the host allows.
