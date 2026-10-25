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
  - The fan-out never exceeds the host's concurrency ceiling; a request above it is clamped and the clamp is reported on the snapshot as `clamped_browser_count` (0 when no clamp happened).
  - A browser count below one is clamped to one rather than producing an empty fan-out.
  - When the session pool offers fewer healthy sessions (N) than the clamped browser count (B), the runner submits one leg per healthy session and reports the shortfall `session_shortfall = max(0, B - N)` on the snapshot instead of padding or re-using a known-LIMITED session; a pool with zero healthy sessions submits no legs. This is consistent with the session rotation `no_eligible_session` rule: a known-LIMITED session is never submitted through.
  - Each leg runs against its own session, so one leg's rate limit does not stop the others.
  - Legs are bounded by a per-leg retry budget; a leg that exhausts it fails while the rest continue.
- **Edge Cases**: A request above the ceiling and a request below one are both reported on the snapshot, not silently dropped.
- **Error Handling**: A leg that fails records its own error in the snapshot; the fan-out as a whole reports completed with per-leg verdicts.

### FR-SWARM-002: Report fan-out progress

- **Description**: Report the current state of a running fan-out.
- **Input**: The fan-out handle.
- **Output**: A snapshot naming each leg's status, its session, and its response path.
- **Business Rules**:
  - A snapshot is a read that never mutates the fan-out.
  - A leg that has not started yet reports `queued` rather than absent.
  - The fan-out progress envelope a poller (MCP `get_job_status` consumer) relies on the snapshot. Run-level fields: `swarm_id`, `input_path`, `root_path`, `status` in `queued` / `running` / `completed` / `partial` / `failed` / `cancelled` (`completed` when every leg succeeded, `partial` when some failed, `cancelled` when stopped), `max_attempts`, `browser_concurrency`, `clamped_browser_count`, `session_shortfall`, and the `agents` tuple. Per-leg fields: `agent_id` (the role), `status` in `queued` / `running` / `retrying` / `completed` / `failed` / `cancelled`, `attempt`, `output_path`, `error`, and `duration_sec`. A poller maps the run-level `status` onto the MCP envelope `status` discriminator, maps each `agent.status` onto the per-leg status, and reads `clamped_browser_count` / `session_shortfall` to explain any submitted leg count below the request.
- **Edge Cases**: A snapshot of a fan-out that never started reports no legs.
- **Error Handling**: A snapshot whose handle is unknown reports no legs rather than raising.

### FR-SWARM-003: Share one fan-out state across the seams

- **Description**: Keep the snapshots, per-leg cancel events, attachment handle, and executor of every run in one store the start, progress, and cancel seams all read.
- **Input**: A new run's snapshot with its cancel events and attachment, and every later revision of that snapshot.
- **Output**: The current snapshot of a run, and the stored runtime bindings it needs.
- **Business Rules**:
  - A read-decide-write cycle is applied under one lock, so two legs of the same run cannot lose one another's status update.
  - Every accepted snapshot is persisted to `manifest.json` before the write returns, so a state a caller reads in memory is also readable on disk.
  - A run's executor, cancel events, and attachment are released on cancel; its snapshot is kept so the terminal state stays readable.
- **Edge Cases**: A revision for a run that was never opened is a no-op.
- **Error Handling**: The store never raises for an unknown run; it reports an absent snapshot and an empty event map.

### FR-SWARM-004: Cancel a fan-out

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
| `open_run` | snapshot, per-leg cancel events, attachment | none | none | none | Register a new run and persist it. |
| `get_snapshot` | fan-out handle | swarm snapshot or none | none | none | Read the latest persisted state of a run. |
| `revise` | fan-out handle, transform | revised snapshot or none | none | none | Replace a snapshot atomically under one lock and persist it. |
| `cancel_events` | fan-out handle | per-leg cancel events | none | none | Read the events that stop each leg of a run. |
| `attachment` | fan-out handle | attachment path or none | none | none | Read the material every leg of a run shares. |
| `attach_executor` | fan-out handle, executor | none | none | none | Bind the executor running the legs of a run. |
| `release` | fan-out handle | the released executor or none | none | none | Drop a run's runtime bindings, keeping its snapshot. |

The three consumer seams are separate capabilities and never import one
another, so the state they share — the rows from `open_run` through `release`
— is reached through this one store.

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
