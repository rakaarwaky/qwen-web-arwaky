# SESSION Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The session feature owns the saved browser sessions: initializing the
workspace they live in, keeping the pool that tracks them, checking which
are still signed in, rotating to the next healthy one when one is rate
limited, and deleting one safely. It owns two orchestrators: the session
aggregate the surfaces call, and the setup aggregate that runs the manual
login sequence.

## Functional Requirements

### FR-SESSION-001: Initialize the session workspace

- **Description**: Create the XDG storage directories and the workspace links a run needs.
- **Input**: The target directory the operator named, or the working directory.
- **Output**: The created workspace, or the paths that could not be created.
- **Business Rules**:
  - Session directories are created with owner-only permissions because they hold live login cookies.
  - An existing directory is reused rather than recreated, so an initialized workspace survives re-initialization.
- **Edge Cases**: A directory the host refuses to create surfaces a file error naming the path.
- **Error Handling**: A link that cannot be created surfaces a file error naming the target; the run proceeds with the default location.

### FR-SESSION-002: Validate a saved session

- **Description**: Report whether a saved session is still signed in.
- **Input**: A session request naming the session path.
- **Output**: A session response carrying the validity verdict and the reason.
- **Business Rules**:
  - A session whose profile no longer authenticates is reported invalid rather than repaired, so the operator chooses to re-login.
- **Edge Cases**: A session path that does not exist is reported invalid, not an error.
- **Error Handling**: An inspection that cannot complete surfaces an error naming the path.

### FR-SESSION-003: Keep and rotate the session pool

- **Description**: Track the known sessions and pick the next one a run should use.
- **Input**: A rotation request naming the current session and the pool's health verdicts.
- **Output**: The next session to use, or the reason none is available.
- **Business Rules**:
  - A rate-limited session is skipped in favor of a healthy one; a pool with only rate-limited sessions rotates back to the first and reports the throttle.
  - The pool order is deterministic so a run resolves the same session under the same pool state.
- **Edge Cases**: A pool with one session rotates to that session rather than failing.
- **Error Handling**: A pool that cannot be read surfaces an error naming the pool path.

### FR-SESSION-004: Delete a session safely

- **Description**: Remove a saved session after taking a backup.
- **Input**: A session request naming the session path and whether to bypass the backup guard.
- **Output**: A session response reporting the deletion and the backup taken, or the refusal.
- **Business Rules**:
  - A master profile is never deleted without a backup; the guard refuses unless the operator forces it.
  - A backup is written before the profile is removed, so a failed deletion can still be restored.
- **Edge Cases**: A session that is already absent is reported as deleted rather than an error.
- **Error Handling**: A backup that cannot be written refuses the deletion rather than removing the profile unprotected.

### FR-SESSION-005: Run the manual login sequence

- **Description**: Launch a browser, navigate to the login, wait for the operator, and validate the resulting session.
- **Input**: A setup request naming the profile path, the headless flag, and an optional confirmation wait.
- **Output**: A setup response carrying the profile path and the outcome message.
- **Business Rules**:
  - An already-valid session short-circuits the sequence and says so, instead of opening a login window.
  - The confirmation wait is consulted while the page is live, so the operator's signal is not missed.
- **Edge Cases**: A headless login has no operator to confirm, so it completes as soon as the page authenticates.
- **Error Handling**: A sequence that cannot complete surfaces the reason and leaves the previous session intact.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `init_workspace` | target directory | created workspace | file error | none | Create the storage directories a run needs. |
| `load_pool` | pool path | session pool | file error | none | Read the tracked session pool. |
| `save_pool` | session pool | saved pool | file error | none | Persist the tracked session pool. |
| `list_sessions` | none | session list | none | none | List the tracked sessions. |
| `get_session` | session identifier | session info | not-found error | none | Read one tracked session. |
| `add_session` | session info | session pool | file error | none | Add one session to the pool. |
| `remove_session` | session identifier | session pool | file error | none | Remove one session from the pool. |
| `mark_healthy` | session identifier | session pool | file error | none | Mark one session usable. |
| `mark_limited` | session identifier | session pool | file error | none | Mark one session rate limited. |
| `get_next_healthy_session` | none | session info | no-healthy-session error | none | Return the next usable session. |
| `check_session` | session path | health verdict | file error | none | Report whether one session is still signed in. |
| `check_all_sessions` | pool | health report | file error | none | Report which tracked sessions are usable. |
| `rotate` | rotator request | rotation response | no-healthy-session error | none | Pick the next session a run should use. |
| `register` | run-scoped cancel state | registered verdict | none | none | Register a run's cancel state. |
| `release` | run-scoped cancel state | released verdict | none | none | Release a run's cancel state. |
| `cancel_run` | run-scoped cancel state | cancelled verdict | none | none | Cancel one run. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | session request naming the verb | session response carrying the validity verdict, the pool, or the deletion outcome | not-found, no-healthy-session, file error | none | Single entry point surfaces call to validate, inspect, rotate, or delete. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Surfaces | in | Validate, rotate, or delete a session | no-healthy-session -> surface prompts for a login |
| Prompt orchestrators | out | Obtain a healthy session per run | no-healthy-session -> run fails before the browser launch |
| Login surfaces | in | Drive the manual login sequence | setup failure -> operator retries |
| External monitors | out | Read the tracked pool's state | absent pool -> empty pool, not an error |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Session directory permissions | owner-only (`0700`) on every workspace init | mode check after creation |
| Rotation determinism | the same pool state resolves the same session | repeated-rotation equality check |
| Deletion safety | no profile removed without a written backup | backup presence before removal |

## Test Scenarios

- A workspace init creates owner-only directories and reuses an existing workspace.
- A session whose profile no longer authenticates is reported invalid rather than repaired.
- A pool with one rate-limited and one healthy session rotates to the healthy one.
- A master profile deletion is refused unless the operator forces it.
- A backup write failure refuses the deletion and leaves the profile in place.
- A cancel on a run with no active pipeline is a no-op.

## Assumptions & Constraints

- Session directories hold live login cookies; they are never written to a shared path and never copied into generated output.
- Deleting a session is destructive; the backup guard is the only thing standing between an operator and an unusable workspace.

## Glossary

- **Session pool**: The tracked list of saved browser sessions and their health verdicts.
- **Rotation**: Picking the next session a run should use, skipping rate-limited ones.
- **Backup guard**: The refusal that blocks deleting a master profile without a written backup.
