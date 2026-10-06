# UPDATE Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The update feature keeps the installed package and its browser build in
step, and restores the previous release when the new one fails its health
gate. It owns version discovery, the package upgrade, the browser sync, the
postflight checks, and the rollback path. One orchestrator routes each verb,
so a caller never sequences the steps itself.

## Functional Requirements

### FR-UPDATE-001: Report the installed and latest versions

- **Description**: Report the version currently installed and the version the release source offers.
- **Input**: An update request naming the current-version or check verb.
- **Output**: An update response carrying the installed version and, for a check, the available version and update availability.
- **Business Rules**:
  - An installed version ahead of the offered version is not reported as an available downgrade.
  - A check that cannot reach the version source reports the failure rather than claiming no update is available.
- **Edge Cases**: An unavailable version source reports the reason; it never reports "up to date".
- **Error Handling**: A version-source failure carries the transport reason so the caller can distinguish it from a network failure.

### FR-UPDATE-002: Upgrade the package and sync the browser

- **Description**: Install the new package release and the matching browser build.
- **Input**: An update request naming the upgrade or sync verb and whether to force past a version check.
- **Output**: An update response carrying the per-step outcomes and the health verdict.
- **Business Rules**:
  - The browser build matches the browser version the new package requires; a mismatch is a failed step, not a warning.
  - A failed step stops the sequence and triggers the rollback rather than continuing with a half-upgraded install.
- **Edge Cases**: A step that is already satisfied reports success without redoing the work.
- **Error Handling**: Each failed step carries its own reason and the step that failed, so the operator knows where the upgrade stopped.

### FR-UPDATE-003: Verify the postflight environment

- **Description**: Confirm the upgraded install still resolves its environment before the run is declared healthy.
- **Input**: An update request naming the perform-update verb.
- **Output**: An update report carrying the postflight check as one step.
- **Business Rules**:
  - The health gate is the only authority that decides a release is acceptable; the update path does not second-guess it.
  - A postflight check that cannot run is reported as a step outcome rather than silently skipped.
- **Edge Cases**: A postflight check that passes reports success without redoing the install.
- **Error Handling**: A postflight failure rolls the release back through the same path a health-gate failure uses.

### FR-UPDATE-004: Roll back when the health gate fails

- **Description**: Restore the previous release after a failed health gate.
- **Input**: An update request naming the rollback verb and the version to restore.
- **Output**: An update response carrying the ordered per-step outcomes of the restore.
- **Business Rules**:
  - Rollback runs in reverse order of the upgrade steps, so the install is restored before the browser build.
  - Rollback is attempted once per failed health gate; a second failure surfaces rather than looping.
- **Edge Cases**: A rollback to the version already installed reports that no restore was needed.
- **Error Handling**: Each restore step carries its own reason; a partially restored install surfaces the step that failed and the version now installed.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `current_version` | none | installed version | none | none | Report the installed version. |
| `check_update` | none | update-check result | version-source error | none | Report the version the release source offers. |
| `upgrade_package` | force flag | update step result | update error | none | Install the new package release. |
| `sync_browser` | force flag | update step result | update error | none | Install the matching browser build. |
| `perform_update` | force flag | update report with health verdict | update error | none | Run the whole update sequence. |
| `rollback_to` | previous version | ordered rollback steps | update error | none | Restore the previous release. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | update request naming the verb | update response carrying the verb's result, report, or steps | version-source error, update error | none | Single entry point the update surface calls to run any update verb. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Update surface | in | Run an update or rollback verb | update error -> surface reports the failed step |
| Health gate | out | Decide whether the new release passes | unhealthy -> the aggregate rolls back automatically |
| Version source | in | Supply the available release | version-source error -> check reports the failure |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Rollback ordering | restore steps run in reverse order of the upgrade steps | recorded step order against the expected order |
| Health-gate coverage | a failed gate always triggers a rollback attempt | rollback step count after an injected failure |

## Test Scenarios

- A check whose version source is unreachable reports the failure rather than claiming the install is current.
- A failed upgrade step triggers a rollback instead of continuing the sequence.
- Rollback restores the install before the browser build.
- A postflight failure routes through the same rollback path a health-gate failure uses.
- A rollback with no target version names the reason rather than restoring something arbitrary.

## Assumptions & Constraints

- Upgrading writes outside the repository; it needs explicit operator approval and never runs unattended.
- The health gate is the only authority that decides a release is acceptable; the update path does not second-guess it.

## Glossary

- **Health gate**: The check that decides whether the newly installed release is acceptable.
- **Rollback**: The reverse-ordered restore of the previous release after a failed health gate.
- **Version source**: The remote release listing a check reads.
