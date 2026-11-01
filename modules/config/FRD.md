# CONFIG Functional Requirements Document

## Feature Overview

The config feature turns the operator's environment and parsed arguments into one validated runtime configuration. Seven capability seams answer the questions a run needs — what the host allows, whether a config can run, where its paths point, how many browsers it can carry, what one slot's widget values mean, how the run workspace is initialized, and whether the host is healthy enough to run at all — and the orchestrator folds their answers into a single config the other features read.

## Functional Requirements

### FR-CONFIG-001: Resolve the operator environment

**Description:**

Report what the host's environment resolves to for every policy the runtime obeys.

#### Business Logic

- An explicit environment switch outranks host detection for the sandbox verdict, so an operator can pin a mode the host would otherwise choose.
- An unparseable or non-positive ceiling falls back to the built-in default instead of failing the boot.

#### Edge Cases

- A non-Linux host reports the sandbox as available; a host whose seccomp filter is disabled reports the sandbox as unavailable.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The process environment, read through the environment seam. |
| **Output** | A sandbox verdict, a response-wait ceiling, a worker cap, a Swarm concurrency cap, and the pinned model name. |
| **Protocol** | `IConfigReadProtocol` / `IConfigInspectProtocol` — the config capability seams. |
| **Method** | `sandbox_report`, `max_workers`, `model`, `request_timeout_sec`, `swarm_concurrency`, `swarm_headless` |
| **Event** | none |
| **Error** | A ceiling that cannot be read at all is not an error; the default applies and the pipeline boots. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An environment override is set | The config resolves | The override outranks host detection for the sandbox verdict |

#### Metric

| Target Metric | Value |
| --- | --- |
| Ceiling default-fallback accuracy | 100% |

### FR-CONFIG-002: Report every problem that keeps a config from running

**Description:**

Return all configuration problems at once instead of raising on the first.

#### Business Logic

- Field minimums are checked against the same thresholds the config itself enforces, so a config that built successfully produces only path findings.
- Findings carry the category that maps onto the operator runbook, so a message can name the doc that fixes it.

#### Edge Cases

- A config with no problems produces an empty finding list, not an error.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A built runtime configuration. |
| **Output** | The list of findings, each with a category, a severity, and an operator-facing sentence. |
| **Protocol** | `IConfigValidateProtocol` — the config capability seam. |
| **Method** | `validate` |
| **Event** | none |
| **Error** | No finding is raised as an exception; the caller decides whether a warning blocks the run. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A config with several invalid fields | The validator runs | Every finding is reported in one call |

#### Metric

| Target Metric | Value |
| --- | --- |
| Finding completeness | 100% |

### FR-CONFIG-003: Resolve config paths and prove the host can use them

**Description:**

Report every path a config names with its existence and writability verdict.

#### Business Logic

- A directory the run has not created yet is not a problem when its nearest existing ancestor accepts a write.
- A read-only field only has to exist; a written field also has to accept a write.

#### Edge Cases

- A field the config left unset is skipped rather than reported as missing.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A built runtime configuration. |
| **Output** | One resolved path per named field, plus the problems found while resolving them. |
| **Protocol** | `IConfigPathProtocol` — the config capability seam. |
| **Method** | `resolve_paths` |
| **Event** | none |
| **Error** | A path that cannot be inspected at all is reported as a finding naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A not-yet-existing output directory | The resolver runs | The path is accepted when its nearest existing ancestor accepts a write |

#### Metric

| Target Metric | Value |
| --- | --- |
| Path verdict accuracy | 100% |

### FR-CONFIG-004: Report host capacity

**Description:**

Report how many concurrent browsers the host can carry.

#### Business Logic

- The ceiling is derived from the host, so the same config never promises more parallelism than the machine can run.

#### Edge Cases

- A host that reports no usable memory falls back to the single-worker default.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The host's CPU and memory characteristics. |
| **Output** | A capacity report naming the recommended worker ceiling. |
| **Protocol** | `IConfigInspectProtocol` — the config capability seam. |
| **Method** | `report` |
| **Event** | none |
| **Error** | Capacity detection failure yields the conservative default rather than aborting the boot. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A host with no usable memory | The inspector runs | The ceiling falls back to the single-worker default |

#### Metric

| Target Metric | Value |
| --- | --- |
| Capacity-fallback accuracy | 100% |

### FR-CONFIG-005: Resolve a slot's widget values into a run plan

**Description:**

Turn the raw values one interactive slot holds into an executable run plan, and discover the batch prompts a folder input names.

#### Business Logic

- One place decides what a slot's values mean, so the interactive surface and the non-interactive path cannot resolve the same values differently.
- Folder discovery respects the configured depth limits and sorts prompts deterministically.

#### Edge Cases

- A folder holding no prompts yields an empty list rather than an error; a depth violation is reported against the file that caused it.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The slot's raw widget values, or a folder path. |
| **Output** | A run plan naming the verb, paths, and flags; or the ordered list of batch prompts a folder holds. |
| **Protocol** | `IConfigPlanProtocol` — the config capability seam. |
| **Method** | `resolve_slot_run_plan`, `discover_batch_prompts` |
| **Event** | none |
| **Error** | A folder that cannot be read surfaces a file error naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A folder input holding three prompts | Discovery runs | The three prompts are listed in a deterministic order |

#### Metric

| Target Metric | Value |
| --- | --- |
| Deterministic batch-prompt ordering | 100% |

### FR-CONFIG-006: Initialize the run workspace

**Description:**

Create the XDG storage directories, provision SKILL.md, create `.qwen-web-arwaky` symlinks, and write a self-contained nested `.qwen-web-arwaky/.gitignore` so a run has the local paths it expects.

#### Business Logic

- Session directories are created with owner-only permissions because they hold live login cookies.
- An existing directory is reused rather than recreated, so an initialized workspace survives re-initialization.

#### Edge Cases

- A directory the host refuses to create surfaces a file error naming the path.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The target directory the operator named, or the working directory. |
| **Output** | The created workspace, or the paths that could not be created. |
| **Protocol** | `IConfigWorkspaceProtocol` — the config capability seam. |
| **Method** | `init_workspace` |
| **Event** | none |
| **Error** | A link that cannot be created surfaces a file error naming the target; the run proceeds with the default location. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A fresh workspace init | The initializer runs | Owner-only session directories are created and existing paths are reused |

#### Metric

| Target Metric | Value |
| --- | --- |
| Workspace-init idempotency | 100% |

### FR-CONFIG-007: Probe host health for the update smoke gate

**Description:**

Run the non-interactive doctor diagnostics and report each as a record.

#### Business Logic

- The checks run at gate-execution time so a post-update gate reflects the post-upgrade state.
- An empty session pool is a legitimate "no session" result, not a probe failure.

#### Edge Cases

- A host that cannot provide a Chromium OS sandbox reports the sandbox as disabled with the deciding reason; a production host with no error tracking reports a warning, not a failure.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The process environment and host state; optionally the session pool aggregate. |
| **Output** | A tuple of health-probe records, each naming the check, its pass/fail verdict, an operator sentence, and a severity. |
| **Protocol** | `IConfigDoctorProtocol` — the config capability seam. |
| **Method** | `probe` |
| **Event** | none |
| **Error** | A check that cannot be probed reports the probe error in the detail sentence rather than raising. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A host without a Chromium OS sandbox | The probe runs | The sandbox is reported as disabled with the deciding reason |

#### Metric

| Target Metric | Value |
| --- | --- |
| Probe-report accuracy | 100% |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `ConfigOrchestrator` |
| Aggregate | `IConfigAggregate` |
| Method | `execute` |
| Request | `ConfigRequest` — names the config mode |
| Response | `ConfigResponse` — carries one validated runtime configuration |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
