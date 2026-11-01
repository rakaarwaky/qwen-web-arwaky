# UPDATE Functional Requirements Document

## Feature Overview

The update feature keeps the installed package and its browser build in step
and restores the previous release when the new one fails its health gate.
It owns version discovery, the package upgrade, the browser sync, the
postflight checks, and the rollback path. One orchestrator routes each verb
to `IUpdateAggregate.execute`, so a caller never sequences the steps itself.

## Functional Requirements

### FR-UPDATE-001: Report the installed and latest versions

**Description:**

Report the version currently installed and the version the release source
offers.

#### Business Logic

- An installed version ahead of the offered version is not reported as an available downgrade.
- A check that cannot reach the version source reports the failure rather than claiming no update is available.

#### Edge Cases

- An unavailable version source reports the reason; it never reports "up to date".

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | An update request naming the current-version or check verb. |
| **Output** | An update response carrying the installed version and, for a check, the available version and update availability. |
| **Protocol** | `IUpdateManagerProtocol` — the version discovery and check seam. |
| **Method** | `current_version`, `check_update`. |
| **Event** | None — the version report is the observable result. |
| **Error** | A version-source failure carries the transport reason so the caller can distinguish it from a network failure. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A check whose version source is unreachable | `check_update` runs | It reports the failure rather than claiming the install is current |

#### Metric

| Target Metric | Value |
| --- | --- |
| Version-report accuracy | 100% |

### FR-UPDATE-002: Upgrade the package and sync the browser

**Description:**

Install the new package release and the matching browser build.

#### Business Logic

- The browser build matches the browser version the new package requires; a mismatch is a failed step, not a warning.
- A failed step stops the sequence and triggers the rollback rather than continuing with a half-upgraded install.

#### Edge Cases

- A step that is already satisfied reports success without redoing the work.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | An update request naming the upgrade or sync verb and whether to force past a version check. |
| **Output** | An update response carrying the per-step outcomes and the health verdict. |
| **Protocol** | `IUpdateManagerProtocol` — the package upgrade and browser-sync seam. |
| **Method** | `upgrade_package`, `sync_browser`, `perform_update`. |
| **Event** | `update_completed` — emitted when the sequence finishes. |
| **Error** | Each failed step carries its own reason and the step that failed, so the operator knows where the upgrade stopped. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A failed upgrade step | The sequence runs | It triggers a rollback instead of continuing |
| A step already satisfied | The sequence runs | It reports success without redoing the work |

#### Metric

| Target Metric | Value |
| --- | --- |
| Browser-build/package-version match | 100% |

### FR-UPDATE-003: Verify the postflight environment

**Description:**

Confirm the upgraded install still resolves its environment before the run
is declared healthy.

#### Business Logic

- The health gate is the only authority that decides a release is acceptable; the update path does not second-guess it.
- A postflight check that cannot run is reported as a step outcome rather than silently skipped.

#### Edge Cases

- A postflight check that passes reports success without redoing the install; a postflight failure rolls the release back through the same path a health-gate failure uses.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | An update request naming the perform-update verb. |
| **Output** | An update report carrying the postflight check as one step. |
| **Protocol** | `IUpdateManagerProtocol` — the postflight health-gate seam. |
| **Method** | `perform_update`. |
| **Event** | `health_gate_passed` — emitted when the postflight check confirms the release. |
| **Error** | A postflight failure rolls the release back through the same path a health-gate failure uses. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A postflight check that cannot run | `perform_update` runs | It is reported as a step outcome rather than silently skipped |

#### Metric

| Target Metric | Value |
| --- | --- |
| Health-gate coverage | A failed gate always triggers a rollback attempt |

### FR-UPDATE-004: Roll back when the health gate fails

**Description:**

Restore the previous release after a failed health gate.

#### Business Logic

- Rollback runs in reverse order of the upgrade steps, so the install is restored before the browser build (package restore, dependency snapshot reconciliation, browser sync).
- Rollback is attempted once per failed health gate; a second failure surfaces rather than looping.
- Rollback status is classified and reported on the surface as one of `none`, `full`, `partial`, or `skipped`:
  - When all executed restore steps succeed, the surface reports `Rolled back : yes (full)` and sets the rolled-back outcome to true.
  - When package code is restored but browser synchronization fails, the surface reports `Rolled back : yes (partial)` and displays remediation instructions to run `update --force`.
  - When rollback cannot proceed due to an unresolvable version, an editable development checkout, or an unpinnable source, the surface reports `Rolled back : no (skipped)` and provides actionable manual recovery commands.
  - When invoked explicitly via the rollback CLI flag with a target version, the surface reports the execution status and detail of each restore step in order.
  - When invoked with a missing target version, the surface rejects the invocation with an actionable error.

#### Edge Cases

- A rollback to the version already installed reports that no restore was needed.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | An update request naming the rollback verb and the version to restore. |
| **Output** | An update response carrying the ordered per-step outcomes of the restore. |
| **Protocol** | `IUpdateManagerProtocol` — the reverse-ordered restore seam. |
| **Method** | `rollback_to`. |
| **Event** | `rollback_completed` — emitted when the restore finishes. |
| **Error** | Each restore step carries its own reason; a partially restored install surfaces the step that failed and the version now installed. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A failed health gate | `rollback_to` runs | The install is restored before the browser build in reverse order |
| A rollback with no target version | `rollback_to` runs | It names the reason rather than restoring something arbitrary |
| An editable install | `rollback_to` runs | It refuses automated reinstall and provides manual git checkout instructions |

#### Metric

| Target Metric | Value |
| --- | --- |
| Rollback ordering | Restore steps run in reverse order of the upgrade steps |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `UpdateOrchestrator` |
| Aggregate | `IUpdateAggregate` |
| Method | `execute` |
| Request | `UpdateRequest` — verbs current-version, check, upgrade, sync, perform-update, rollback |
| Response | `UpdateResponse` — carries the verb's result, report, or ordered rollback steps |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
