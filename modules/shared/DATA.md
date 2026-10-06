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
