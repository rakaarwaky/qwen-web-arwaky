# SWARM Functional Requirements Document

## Feature Overview

The swarm feature fans one prompt out across several browser sessions and
runs them concurrently. It owns the fan-out runner, the progress snapshot a
caller polls, and the cancellation path. Callers start a fan-out, read a
snapshot while it runs, and cancel it; they never own a browser or a thread.
The orchestrator routes verbs to `ISwarmAggregate.execute`, backed by the
swarm-runner capability and one shared fan-out-state store.

## Functional Requirements

### FR-SWARM-001: Start a fan-out

**Description:**

Run one prompt across the requested number of browsers concurrently.

#### Business Logic

- The fan-out never exceeds the host's concurrency ceiling; a request above it is clamped and the clamp is reported on the snapshot as `clamped_browser_count` (0 when no clamp happened).
- A browser count below one is clamped to one rather than producing an empty fan-out.
- When the session pool offers fewer healthy sessions (N) than the clamped browser count (B), the runner submits one leg per healthy session and reports the shortfall `session_shortfall = max(0, B - N)` on the snapshot instead of padding or re-using a known-LIMITED session; a pool with zero healthy sessions submits no legs. This is consistent with the session rotation `no_eligible_session` rule: a known-LIMITED session is never submitted through.
- Each leg runs against its own session, so one leg's rate limit does not stop the others.
- Legs are bounded by a per-leg retry budget; a leg that exhausts it fails while the rest continue.

#### Edge Cases

- A request above the ceiling and a request below one are both reported on the snapshot, not silently dropped.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A swarm request naming the verb, the prompt source, the browser count, and the run configuration. |
| **Output** | A swarm response carrying the fan-out handle, or the reason it could not start. |
| **Protocol** | `ISwarmRunnerProtocol` — the concurrent fan-out execution seam. |
| **Method** | `start`, `browser_concurrency`. |
| **Event** | `dispatch_acknowledged` — emitted when the fan-out is accepted. |
| **Error** | A leg that fails records its own error in the snapshot; the fan-out as a whole reports completed with per-leg verdicts. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A fan-out above the host ceiling | The runner starts it | The browser count is clamped and the clamp is reported on the snapshot |
| A leg that fails | The other legs run | The failed leg records its own error while the rest complete |

#### Metric

| Target Metric | Value |
| --- | --- |
| Concurrency clamp | A request above the ceiling never opens more browsers than the ceiling |

### FR-SWARM-002: Report fan-out progress

**Description:**

Report the current state of a running fan-out.

#### Business Logic

- A snapshot is a read that never mutates the fan-out.
- A leg that has not started yet reports `queued` rather than absent.
- The snapshot carries run-level fields (`swarm_id`, `input_path`, `root_path`, `status` in `queued` / `running` / `completed` / `partial` / `failed` / `cancelled`, `max_attempts`, `browser_concurrency`, `clamped_browser_count`, `session_shortfall`, and the `agents` tuple) and per-leg fields (`agent_id`, `status`, `attempt`, `output_path`, `error`, `duration_sec`).

#### Edge Cases

- A snapshot of a fan-out that never started reports no legs; a snapshot whose handle is unknown reports no legs rather than raising.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The fan-out handle. |
| **Output** | A snapshot naming each leg's status, its session, and its response path. |
| **Protocol** | `ISwarmRunnerProtocol` — the fan-out progress read seam. |
| **Method** | `snapshot`. |
| **Event** | None — the snapshot is the observable result. |
| **Error** | None — an unknown handle reports no legs rather than raising. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A leg that has not started | A snapshot is read | It reports `queued` rather than absent |
| A fan-out that never started | A snapshot is read | It reports no legs |

#### Metric

| Target Metric | Value |
| --- | --- |
| Snapshot purity | A snapshot never mutates the fan-out |

### FR-SWARM-003: Share one fan-out state across the seams

**Description:**

Keep the snapshots, per-leg cancel events, attachment handle, and executor
of every run in one store the start, progress, and cancel seams all read.

#### Business Logic

- A read-decide-write cycle is applied under one lock, so two legs of the same run cannot lose one another's status update.
- Every accepted snapshot is persisted to `manifest.json` before the write returns, so a state a caller reads in memory is also readable on disk.
- A run's executor, cancel events, and attachment are released on cancel; its snapshot is kept so the terminal state stays readable.
- The three consumer seams are separate capabilities and never import one another, so the shared state is reached through this one store.

#### Edge Cases

- A revision for a run that was never opened is a no-op; the store never raises for an unknown run — it reports an absent snapshot and an empty event map.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A new run's snapshot with its cancel events and attachment, and every later revision of that snapshot. |
| **Output** | The current snapshot of a run, and the stored runtime bindings it needs. |
| **Protocol** | `ISwarmStateProtocol` — the shared fan-out state store seam. |
| **Method** | `open_run`, `get_snapshot`, `revise`, `cancel_events`, `attachment`, `attach_executor`, `release`. |
| **Event** | None — the persisted snapshot is the observable result. |
| **Error** | None — an unknown run reports an absent snapshot and an empty event map rather than raising. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| Two legs of the same run revise at once | The store applies both | No leg loses the other's status update |
| A run that was never opened | A revision is requested | The revision is a no-op |

#### Metric

| Target Metric | Value |
| --- | --- |
| Fan-out state durability | Every accepted snapshot is readable on disk after the write |

### FR-SWARM-004: Cancel a fan-out

**Description:**

Stop every leg of a running fan-out.

#### Business Logic

- A leg that already reached a terminal state is not reported as stopped.
- Cancellation does not roll back legs that already wrote their response file.

#### Edge Cases

- A cancel on a completed fan-out reports zero; a cancel whose handle is unknown reports zero rather than raising.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The fan-out handle. |
| **Output** | The number of legs stopped. |
| **Protocol** | `ISwarmRunnerProtocol` — the fan-out cancellation seam. |
| **Method** | `cancel`. |
| **Event** | `generation_finished` — emitted when the fan-out reaches a terminal state. |
| **Error** | None — an unknown handle reports zero stopped legs rather than raising. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A running fan-out | Cancel is requested | Every running leg stops and the written response files stay in place |
| A completed fan-out | Cancel is requested | Zero stopped legs are reported |

#### Metric

| Target Metric | Value |
| --- | --- |
| Cancel completeness | Every running leg stops |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `SwarmOrchestrator` |
| Aggregate | `ISwarmAggregate` |
| Method | `execute` |
| Request | `SwarmRequest` — verbs start, snapshot, cancel |
| Response | `SwarmResponse` — carries the handle, the snapshot, or the stopped-leg count |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
