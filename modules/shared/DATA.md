# DATA — Shared Kernel

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## Data Overview

The shared kernel owns every value object, entity, constant, event, and
protocol the feature modules import. Surfaces and agents read these shapes
unchanged; only the kernel writes them. A reader should be able to learn every
data contract here without opening source files.

## Data Domain

| ID | Field | Type | Description |
|----|-------|------|-------------|
| D-01 | AppConfig | VO | One validated run configuration: mode, paths, model, headless flag, sandbox verdict, request-timeout ceiling, worker counts. Built once at boot by the config orchestrator, then read-only. |
| D-02 | HeadlessFlag | Enum VO | Browser visibility policy for a run; `True` never spawns a GUI context. |
| D-03 | JobRecord | Entity | One queued background job: identifier, verb, input paths, status, timestamps, worker ownership. Persisted by the jobs kernel; the status JSON is the inter-process handoff. |
| D-04 | JobRequest / JobResponse | VO | Verb-and-payload pair the MCP and TUI surfaces hand to the job aggregate; the response carries the identifier or a structured error. |
| D-05 | PromptRequest / PromptResponse | VO | One prompt-verb request (direct, file, attachment) and its result: output path, extraction status, or error reason. |
| D-06 | SessionRequest / SessionResponse | VO | Session check/setup/delete verbs and the stored-state verdict they return. |
| D-07 | ObservabilityRequest / ObservabilityResponse | VO | Logging verbs: which log file to open, which run id to stamp, and the resulting status paths. |
| D-08 | ConfigRequest / ConfigResponse | VO | Mode plus operator overrides in; one `AppConfig` out. |
| D-09 | SwarmRequest / SwarmResponse / SwarmSnapshot | VO | Fan-out request (browser count, prompt source), progress snapshot, and terminal verdict. |
| D-10 | UpdateRequest / UpdateResponse | VO | Update/rollback verb and the health-gate outcome that decides whether the previous version is restored. |
| D-11 | Event | Event | Lifecycle records (`dispatch_acknowledged`, `failed`, `generation_finished`) emitted by the job and prompt kernels; consumers filter on name and payload. |
| D-12 | CircuitBreaker / RateLimiter | Entity | Shared throttling state: a sliding-window limiter and an open/closed breaker that trip on consecutive failures. |
| D-13 | LifecycleEmitter | Entity | The single emit point for D-11 events; every kernel that reports progress routes through it so consumers see one ordering. |
| D-14 | RunContext | VO | Per-run stamping data: run id, start time, output paths, log file; attached to every event so logs are greppable by run. |

## Assumptions & Constraints

- Value objects are frozen after construction; a feature that mutates one is
  violating the kernel contract.
- Event names are a closed vocabulary; adding a name requires a new row here.
- Paths carried in VOs are absolute; relative paths are a surface-layer bug.
- Status JSON written by the jobs kernel is read by humans and agents alike;
  field removal is a breaking change.
### Rate-limiter window semantics

The shared kernel owns the sliding-window throttle state (D-12) that every
prompt and Swarm dispatch gate reads. Its window semantics are fixed here so
a caller can reason about how long a run parks, and when a window exhaustion
surfaces as a stable failure reason, without re-deriving the rule from the
shared entity that defines it. Each value below is cited to the kernel
symbol and the role that owns it.

- **Window size.** The limiter is a sliding 60-second window owned by the
  shared `RateLimiter` entity. A request that acquires a slot inside the
  window counts against the `max_per_minute` limit; slots that fall out of
  the window stop counting. The default limit is 60 requests per minute,
  carried on the shared config VO `AppConfig.rate_limit_per_minute`.
- **Window reset.** A window reset is decided by the limiter itself, not by
  the caller: `RateLimiter.try_acquire` prunes timestamps older than
  `now - 60.0` on every call, so the window slides forward on each acquire.
  There is no explicit reset call; the window resets incrementally as old
  slots age out of the 60-second lookback. A caller that sees a wait-seconds
  value from `try_acquire` parks for that many seconds and re-enters the
  limiter, at which point the window has advanced.
- **Interaction with the per-attempt response ceiling.** The wall-clock
  response ceiling (CONFIG-02's `request_timeout_sec`, resolved by the
  shared environment utility and carried on `AppConfig.request_timeout`) is
  absolute and terminal per attempt: a single attempt cannot exceed it even
  if the limiter has slots free. The limiter only gates *when* an attempt
  may start; the ceiling bounds *how long* one attempt runs. A run whose
  attempts are repeatedly cut by the ceiling burns limiter slots faster and
  parks longer on the next attempt.
- **Interaction with the retry budget.** The dispatch retry budget
  (FR-PROMPT-006 / PROMPT-01, resolved by the shared retry-budget utility)
  governs how many *extra dispatch attempts* the shared-flow dispatcher may
  grant after the event-driven stall detector (`stall_timeout_sec`) cuts a
  stream. The limiter is a throttle on total requests; the retry budget is a
  cap on how many of those requests are *retried after a stall*. A run that
  exhausts its retry budget stops re-attempting, but the limiter still
  applies to any remaining in-flight attempts that park on a full window.
- **Stable failure reason on window exhaustion.** When the window is full,
  `RateLimiter.try_acquire` returns a wait-seconds value (never blocks). The
  dispatch loop surfaces this as a `RateLimitError` with `retry_after_sec`
  set to the limiter's wait value, and the MCP surface maps it to the
  `RATE_LIMITED` envelope code. The stable reason string a poller can branch
  on is `"rate_limit"` in the error-category vocabulary (the shared
  environment utility's runbook index maps `rate_limit` to the rate-limit
  runbook), and the retry hint is the limiter's `retry_after_sec`.

Owners of each value:

| Value | Owner |
|---|---|
| Sliding-window limiter, `max_per_minute`, 60-second lookback | shared `RateLimiter` entity |
| `rate_limit_per_minute` default 60 | shared `AppConfig` VO |
| `request_timeout_sec` ceiling and env override | shared environment utility (CONFIG-02) |
| Dispatch retry budget default 0 and env override | shared retry-budget utility (FR-PROMPT-006) |
| `RateLimitError` and `retry_after_sec` | shared error taxonomy |
| `RATE_LIMITED` envelope and `rate_limit` runbook mapping | MCP surface + shared environment utility |
