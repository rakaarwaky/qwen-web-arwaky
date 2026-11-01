# DATA — Shared Kernel

## Data Overview

The shared kernel owns every value object, entity, constant, event, and protocol the feature modules import. Surfaces and agents read these shapes unchanged; only the kernel writes them. A reader should be able to learn every data contract here without opening source files.

## Data Requirements

### DT-SHARED-001: AppConfig

| Type | Description |
| --- | --- |
| VO | One validated run configuration: mode, paths, model, headless flag, sandbox verdict, request-timeout ceiling, worker counts. Built once at boot by the config orchestrator, then read-only. |

### DT-SHARED-002: HeadlessFlag

| Type | Description |
| --- | --- |
| Enum VO | Browser visibility policy for a run; `True` never spawns a GUI context. |

### DT-SHARED-003: JobRecord

| Type | Description |
| --- | --- |
| Entity | One queued background job: identifier, verb, input paths, status, timestamps, worker ownership. Persisted by the jobs kernel; the status JSON is the inter-process handoff. |

### DT-SHARED-004: JobRequest / JobResponse

| Type | Description |
| --- | --- |
| VO | Verb-and-payload pair the MCP and TUI surfaces hand to the job aggregate; the response carries the identifier or a structured error. |

### DT-SHARED-005: PromptRequest / PromptResponse

| Type | Description |
| --- | --- |
| VO | One prompt-verb request (direct, file, attachment) and its result: output path, extraction status, or error reason. |

### DT-SHARED-006: SessionRequest / SessionResponse

| Type | Description |
| --- | --- |
| VO | Session check/setup/delete verbs and the stored-state verdict they return. |

### DT-SHARED-007: ObservabilityRequest / ObservabilityResponse

| Type | Description |
| --- | --- |
| VO | Logging verbs: which log file to open, which run id to stamp, and the resulting status paths. |

### DT-SHARED-008: ConfigRequest / ConfigResponse

| Type | Description |
| --- | --- |
| VO | Mode plus operator overrides in; one `AppConfig` out. |

### DT-SHARED-009: SwarmRequest / SwarmResponse / SwarmSnapshot

| Type | Description |
| --- | --- |
| VO | Fan-out request (browser count, prompt source), progress snapshot, and terminal verdict. |

### DT-SHARED-010: UpdateRequest / UpdateResponse

| Type | Description |
| --- | --- |
| VO | Update/rollback verb and the health-gate outcome that decides whether the previous version is restored. |

### DT-SHARED-011: Event

| Type | Description |
| --- | --- |
| Event | Lifecycle records (`dispatch_acknowledged`, `failed`, `generation_finished`) emitted by the job and prompt kernels; consumers filter on name and payload. |

### DT-SHARED-012: CircuitBreaker / RateLimiter

| Type | Description |
| --- | --- |
| Entity | Shared throttling state: a sliding-window limiter and an open/closed breaker that trip on consecutive failures. |

### DT-SHARED-013: LifecycleEmitter

| Type | Description |
| --- | --- |
| Entity | The single emit point for D-11 events; every kernel that reports progress routes through it so consumers see one ordering. |

### DT-SHARED-014: RunContext

| Type | Description |
| --- | --- |
| VO | Per-run stamping data: run id, start time, output paths, log file; attached to every event so logs are greppable by run. |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
