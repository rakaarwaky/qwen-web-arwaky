# SESSION Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The session feature owns the saved browser sessions: keeping the pool that
tracks them, checking which are still signed in, rotating to the next
healthy one when one is rate limited, and deleting one safely. It owns one
aggregate the surfaces call — the session aggregate — which implements all
eight session verbs, including the setup flow's manual login.

Workspace initialization (XDG directories, `.qwen-web-arwaky` symlinks, SKILL.md
provisioning, `.gitignore` management) moved to the config feature
(`modules/config`), and the targeted run-cancel registry moved to the prompt
feature (`modules/prompt`). The session module now holds only the session
pool, health checking, rotation, renewal, deletion, and login.

## Functional Requirements

### FR-SESSION-001: Validate a saved session

- **Description**: Report whether a saved session is still signed in.
- **Input**: A session request naming the session path.
- **Output**: A session response carrying the validity verdict and the reason.
- **Business Rules**:
  - A session whose profile no longer authenticates is first offered a transparent token renewal (while the refresh token is still valid); only when renewal is impossible is it reported invalid, so the operator chooses to re-login.
- **Edge Cases**: A session path that does not exist is reported invalid, not an error.
- **Error Handling**: An inspection that cannot complete surfaces an error naming the path.

### FR-SESSION-002: Keep and rotate the session pool

- **Description**: Track the known sessions and pick the next one a run should use; report reasoned health verdicts with sub-cause and recovery.
- **Input**: A rotation request naming the sessions already tried and the pool's health verdicts.
- **Output**: The next session to use, or the reason none is available (`no_eligible_session` with `reason` and `recovery_action`); or a `SessionHealthResult` with status (`ACTIVE`, `LIMITED`, `AUTH_REQUIRED`), reason, evidence, and recovery action.
- **Business Rules**:
  - `ACTIVE` only from a successful authenticated probe.
  - `LIMITED` only from observed provider-limit evidence (limit banner/signal with `QUOTA` reason); a probe failure MUST NOT overwrite a confirmed LIMITED verdict with invented quota evidence.
  - `AUTH_REQUIRED` for any other failed probe: expired login (`EXPIRED`), browser launch failure (`LAUNCH_FAILURE`), network error (`NETWORK`), or timeout (`TIMEOUT`).
  - A rate-limited session is skipped. If no eligible session remains, return an explicit `no_eligible_session` outcome without submitting; never submit through a known-LIMITED profile.
  - The pool order is deterministic so a run resolves the same session under the same pool state.
  - Cross-account rotation on quota is permitted for authorized accounts only (owned/controlled by the operator). See `docs/MULTI_ACCOUNT_ROTATION.md` policy gate (2026-10-18).
  - The pool file is shared by the long-lived MCP server and short-lived CLI commands, so every load→mutate→save cycle holds an exclusive advisory lock (`sessions.json.lock`, `fcntl.flock` on POSIX / `msvcrt.locking` on Windows) for its full duration; the atomic `os.replace` swap is kept.
  - A CAPTCHA or provider access-control stop halts immediately; no bypass attempt is made.
  - No promise that a provider quota resets by a specific time; the operator decides when to retry.
- **Edge Cases**:
  - An empty pool returns `no_eligible_session` with reason `empty_pool`.
  - A single-limited pool returns `no_eligible_session` with reason `all_sessions_limited`.
  - An all-limited pool returns `no_eligible_session` with reason `all_sessions_limited`.
  - A pool where every session is in `exclude_ids` returns `no_eligible_session` with reason `all_sessions_excluded`.
  - A mixed pool (some healthy, some limited) returns the next healthy session.
  - A session that is `UNKNOWN` (not yet probed) and whose probe fails transiently is reported `AUTH_REQUIRED`, never `LIMITED`.
  - For the `check_health` verb, `SessionResponse.valid` indicates pool availability (`healthy_count > 0`): True when at least one session in the pool is ready to accept requests; False when the pool is empty or every session is limited or unauthenticated.
- **Error Handling**: A transient read failure (OSError) surfaces an error naming the pool path without quarantining; only parse errors (JSONDecodeError/KeyError/TypeError/ValueError) quarantine to `sessions.json.corrupt-<timestamp>`, log a warning naming the path, and rebuild from on-disk profile directories. Missing browser configuration reports `AUTH_REQUIRED` with `LAUNCH_FAILURE` reason.

### FR-SESSION-003: Delete a session safely

- **Description**: Remove a saved session after taking a backup.
- **Input**: A session request naming the session path or name, and whether to bypass the backup guard.
- **Output**: A session response reporting the deletion and the backup taken, or the refusal.
- **Business Rules**:
  - A master profile is never deleted without a backup; the guard refuses unless the operator forces it.
  - A backup is written before the profile is removed, so a failed deletion can still be restored.
  - The deletion target is always explicit: `session_path` wins, else the pool entry is resolved by `name`. A delete naming neither refuses; a target is never inferred from pool order.
  - `force=True` bypasses the guard, and the bypass is logged as a warning naming the target.
- **Edge Cases**: A session that is already absent is reported as "nothing deleted" rather than a false success.
- **Error Handling**: A backup that cannot be written (permission, ENOSPC, read-only filesystem) refuses the deletion rather than removing the profile unprotected.

### FR-SESSION-004: Run the manual login sequence

- **Description**: Launch a browser, navigate to the login, wait for the operator, and validate the resulting session.
- **Input**: A setup request naming the profile path, the headless flag, and an optional confirmation wait.
- **Output**: A setup response carrying the profile path and the outcome message.
- **Business Rules**:
  - The login verb always opens a visible browser window (AES205); the already-valid fast-path belongs to the validate/check_health verbs, and `validate` reports a valid session without launching a login window.
  - The confirmation wait is consulted while the page is live, so the operator's signal is not missed.
  - Wait policy: the login loop terminates on login confirmation, page close, or its own wait ceiling — never earlier on the generic run timeout. The ceiling is `DEFAULT_LOGIN_WAIT_TIMEOUT_SEC` (1800s), overridable via `QWEN_LOGIN_WAIT_SEC`, and the CLI banner states the same window.
- **Edge Cases**: A headless login has no operator to confirm, so it completes as soon as the page authenticates. An `AppConfig.timeout` shorter than the login wait ceiling does not truncate the login window, and a non-integer `QWEN_LOGIN_WAIT_SEC` falls back to the default ceiling.
- **Error Handling**: A sequence that cannot complete surfaces the reason and leaves the previous session intact.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `load_pool` | pool path | session pool | file error | none | Read the tracked session pool, quarantining a corrupt file and rebuilding from disk. |
| `save_pool` | session pool | saved pool | file error | none | Persist the tracked session pool atomically (temp file + atomic swap). |
| `list_sessions` | none | session list | none | none | List the tracked sessions. |
| `get_session` | session identifier | session info | not-found error | none | Read one tracked session. |
| `add_session` | session info | session pool | file error | none | Add one session to the pool with a unique ID. |
| `remove_session` | session identifier | session pool | file error | none | Remove one session from the pool. |
| `mark_healthy` | session identifier | session pool | file error | none | Mark one session usable. |
| `mark_limited` | session identifier, optional reason | session pool | file error | none | Mark one session rate limited. |
| `mark_auth_required` | session identifier, optional reason | session pool | file error | none | Mark one session as requiring re-authentication. |
| `get_next_healthy_session` | none | session info | no-healthy-session error | none | Return the next usable session. |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | session request naming the verb | session response carrying the validity verdict, the pool entry, the rotation selection, the deletion outcome, or the health summary | not-found, no-healthy-session, file error | none | Single entry point surfaces call for every session verb: `validate` \| `inspect` \| `rotate` \| `delete` \| `login` \| `list_sessions` \| `remove_session` \| `check_health`. |

Verb contracts (input → output → error), in dispatch order:

| Verb | Input | Output | Error |
|---|---|---|---|
| `validate` | `session_path` | `valid`, `message`, `status`, `reason`, `recovery_action` | path that cannot be inspected |
| `inspect` | `session_path` or `name` | the single pool entry in `sessions`, `message` | `session not found`; missing selector |
| `rotate` | `exclude_ids` | the selected session in `sessions`, or `throttled` with `reason` and `recovery_action` | rotator not wired; rotation failure |
| `delete` | `session_path` or `name`, `force` | `deleted`, `message` | `QwenCliError` naming the refused target |
| `login` | `session_path` or `name`, `wait_for_confirmation` | `valid`, `profile_path`, `message` | login could not complete |
| `list_sessions` | none | the whole pool in `sessions`, `message` | no pool available |
| `remove_session` | `name` | `removed`, `message`, `profile_path` | missing `request.name`; `session not found` |
| `check_health` | none | `health_healthy`, `health_total`, `message`, `status`, `health_results` (each carrying `status`, `reason`, `evidence`, `recovery_action`) | health checker not wired |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Surfaces | in | Validate, inspect, rotate, or delete a session | no-healthy-session -> surface prompts for a login |
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

- A session whose profile no longer authenticates is transparently renewed first; only when renewal is impossible is it reported invalid.
- A pool with one rate-limited and one healthy session rotates to the healthy one.
- A pool with every session rate-limited returns `no_eligible_session` with reason `all_sessions_limited`; `execute_with_rotation` returns an explicit error outcome without submitting.
- A master profile deletion is refused unless the operator forces it.
- A backup write failure refuses the deletion and leaves the profile in place.
- An inspect of a known session returns its pool entry; an inspect naming nothing reports the missing selector.
- A delete of an already-absent profile reports "nothing deleted" rather than a false success.

## Assumptions & Constraints

- Session directories hold live login cookies; they are never written to a shared path and never copied into generated output.
- Deleting a session is destructive; the backup guard is the only thing standing between an operator and an unusable workspace.

## Glossary

- **Session pool**: The tracked list of saved browser sessions and their health verdicts.
- **Rotation**: Picking the next session a run should use, skipping rate-limited ones.
- **Backup guard**: The refusal that blocks deleting a master profile without a written backup.
