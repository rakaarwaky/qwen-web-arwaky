# CONFIG Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The config feature turns the operator's environment and parsed arguments
into one validated runtime configuration. Five capability seams answer the
questions a run needs — what the host allows, whether a config can run,
where its paths point, how many browsers it can carry, and what one slot's
widget values mean — and the orchestrator folds their answers into a single
config the other features read.

## Functional Requirements

### FR-CONFIG-001: Resolve the operator environment

- **Description**: Report what the host's environment resolves to for every policy the runtime obeys.
- **Input**: The process environment, read through the environment seam.
- **Output**: A sandbox verdict, a response-wait ceiling, a worker cap, a Swarm concurrency cap, and the pinned model name.
- **Business Rules**:
  - An explicit environment switch outranks host detection for the sandbox verdict, so an operator can pin a mode the host would otherwise choose.
  - An unparseable or non-positive ceiling falls back to the built-in default instead of failing the boot.
- **Edge Cases**: A non-Linux host reports the sandbox as available; a host whose seccomp filter is disabled reports the sandbox as unavailable.
- **Error Handling**: A ceiling that cannot be read at all is not an error; the default applies and the pipeline boots.

### FR-CONFIG-002: Report every problem that keeps a config from running

- **Description**: Return all configuration problems at once instead of raising on the first.
- **Input**: A built runtime configuration.
- **Output**: The list of findings, each with a category, a severity, and an operator-facing sentence.
- **Business Rules**:
  - Field minimums are checked against the same thresholds the config itself enforces, so a config that built successfully produces only path findings.
  - Findings carry the category that maps onto the operator runbook, so a message can name the doc that fixes it.
- **Edge Cases**: A config with no problems produces an empty finding list, not an error.
- **Error Handling**: No finding is raised as an exception; the caller decides whether a warning blocks the run.

### FR-CONFIG-003: Resolve config paths and prove the host can use them

- **Description**: Report every path a config names with its existence and writability verdict.
- **Input**: A built runtime configuration.
- **Output**: One resolved path per named field, plus the problems found while resolving them.
- **Business Rules**:
  - A directory the run has not created yet is not a problem when its nearest existing ancestor accepts a write.
  - A read-only field only has to exist; a written field also has to accept a write.
- **Edge Cases**: A field the config left unset is skipped rather than reported as missing.
- **Error Handling**: A path that cannot be inspected at all is reported as a finding naming the path.

### FR-CONFIG-004: Report host capacity

- **Description**: Report how many concurrent browsers the host can carry.
- **Input**: The host's CPU and memory characteristics.
- **Output**: A capacity report naming the recommended worker ceiling.
- **Business Rules**: The ceiling is derived from the host, so the same config never promises more parallelism than the machine can run.
- **Edge Cases**: A host that reports no usable memory falls back to the single-worker default.
- **Error Handling**: Capacity detection failure yields the conservative default rather than aborting the boot.

### FR-CONFIG-005: Resolve a slot's widget values into a run plan

- **Description**: Turn the raw values one interactive slot holds into an executable run plan, and discover the batch prompts a folder input names.
- **Input**: The slot's raw widget values, or a folder path.
- **Output**: A run plan naming the verb, paths, and flags; or the ordered list of batch prompts a folder holds.
- **Business Rules**: One place decides what a slot's values mean, so the interactive surface and the non-interactive path cannot resolve the same values differently.
  - Folder discovery respects the configured depth limits and sorts prompts deterministically.
- **Edge Cases**: A folder holding no prompts yields an empty list rather than an error; a depth violation is reported against the file that caused it.
- **Error Handling**: A folder that cannot be read surfaces a file error naming the path.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `sandbox_report` | host environment | sandbox verdict with reason | none | none | Report the sandbox mode Chromium will launch under. |
| `max_workers` | host environment | worker ceiling | none | none | Report the concurrency the host can carry. |
| `model` | host environment | model name | none | none | Report the model the run pins. |
| `request_timeout_sec` | host environment | response-wait ceiling | none | none | Report the wall-clock response ceiling. |
| `swarm_concurrency` | host environment | fan-out ceiling | none | none | Report how many fan-out browsers may run at once. |
| `swarm_headless` | host environment | fan-out browser visibility | none | none | Report whether fan-out browsers open a window. |
| `validate` | built runtime config | list of findings | none | none | Report every problem that blocks a run. |
| `resolve_paths` | built runtime config | resolved paths and findings | none | none | Report each named path and its host verdict. |
| `report` | host characteristics | capacity report | none | none | Report the host's browser capacity. |
| `resolve_slot_run_plan` | slot widget values | run plan | validation error | none | Resolve one slot's values into an executable plan. |
| `discover_batch_prompts` | folder path | ordered prompt paths | file error | none | List the prompts a folder input names. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | config request naming the mode | config response carrying one validated runtime configuration | validation error | none | Single entry point every other feature calls to obtain its config. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Prompt orchestrators | out | Obtain the run configuration | validation error -> caller reports the finding |
| Session orchestrators | out | Obtain sandbox and path verdicts | validation error -> caller refuses the run |
| Doctor surface | in | Read the same verdicts a run will obey | none; diagnostics read only |
| Interactive slot surfaces | in | Resolve slot widget values into a run plan | validation error -> slot reports the offending field |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Config build latency | no filesystem or network probe on the happy path | timing the build seam |
| Finding completeness | every problem reported, not the first | finding count against a seeded multi-fault config |
| Determinism | the same environment yields the same config every build | repeated-build equality check |

## Test Scenarios

- An explicit sandbox switch overrides what the host detection would have chosen.
- An unparseable response ceiling falls back to the default and the pipeline still boots.
- A config whose output directory does not exist yet is accepted when its nearest existing ancestor accepts a write.
- A config with several invalid fields reports every one of them in one call.
- A folder input holding three prompts discovers them in a deterministic order.

## Assumptions & Constraints

- The request-timeout ceiling is wall-clock, not an idle budget: a long thinking phase emits no forward event, so a short ceiling aborts healthy runs.
- The capacity ceiling is advisory. A caller that raises it owns the consequences.

## Glossary

- **Run plan**: The verb, paths, and flags one interactive slot resolves to.
- **Capacity report**: The host's browser concurrency ceiling and how it was derived.
- **Sandbox verdict**: The mode Chromium will launch under, plus the reason it was chosen.
