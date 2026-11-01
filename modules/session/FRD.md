# SESSION Functional Requirements Document

## Feature Overview

The session feature owns the saved browser sessions: keeping the pool that
tracks them, checking which are still signed in, rotating to the next
healthy one when one is rate limited, renewing a stale auth session, and
deleting one safely. It owns one aggregate the surfaces call —
`ISessionAggregate` — whose `execute` door routes a session verb. Workspace
initialization (XDG directories, symlinks, SKILL.md provisioning) lives in
the config feature; the run-cancel registry lives in the prompt feature.
The session module holds only the session pool, health checking, rotation,
renewal, deletion, and login.

## Functional Requirements

### FR-Session-001: Keep and rotate the session pool

**Description:**

Track the known sessions, register new ones, remove them, and mark their
health verdicts; pick the next session a run should use and report reasoned
health verdicts with sub-cause and recovery.

#### Business Logic

- The pool file is advisory. It is not the source of truth for which sessions exist. The session manager scans the session directory for registered session metadata and on-disk Chromium profiles.
- The pool file is locked with an advisory lock (`sessions.json.lock`) during read-modify-write. A stale lock is detected and cleared before recovery.
- Pool file writes are atomic (temp file + `os.replace` swap). A corrupt pool file is quarantined to `sessions.json.corrupt-<timestamp>` and rebuilt from disk.
- Sessions discovered on disk but missing from the pool file are registered with `SessionStatus.AUTH_REQUIRED` (UNKNOWN remains a deprecated read-only alias for legacy pool files).
- Session IDs are unique and never reused; pool order is deterministic: the same pool state resolves the same session.
- A session whose profile no longer authenticates is first offered a transparent token renewal (while the refresh token is still valid); only when renewal is impossible is it reported invalid, so the operator chooses to re-login.
- The session deletion target is always explicit; no wildcard or directory-wide deletion is permitted. A saved Chromium profile is never deleted without a backup, unless the caller passes `force=True`.

#### Edge Cases

- A session path that does not exist is reported invalid, not an error.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A rotation request naming the sessions already tried and the pool's health verdicts; or a register/remove/mark request naming the session. |
| **Output** | The next session to use, or the reason none is available (`no_eligible_session` with `reason` and `recovery_action`); reasoned health verdicts with sub-cause and recovery. |
| **Protocol** | `ISessionAggregate` — the session feature's single aggregate door; the pool verbs are its capability methods. |
| **Method** | `load_pool`, `save_pool`, `add_session`, `remove_session`, `get_session_by_name`, `delete_session_profile`, `mark_healthy`, `mark_limited`, `mark_auth_required`, `get_next_session`. |
| **Event** | `session_rotated` — emitted when the pool resolves the next eligible session. |
| **Error** | An inspection that cannot complete surfaces an error naming the path; a missing master profile deletion is refused without a backup unless `force=True` (`QwenCliError`). |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A pool file that is missing or corrupt | `load_pool` runs | The pool is rebuilt from the on-disk session directory |
| A session added to the pool | `add_session` runs | It is registered with a unique ID and persisted |

#### Metric

| Target Metric | Value |
| --- | --- |
| Pool-file atomic-write correctness | 100% |

### FR-Session-002: Authenticate the session

**Description:**

Report whether the Qwen chat page behind a session is still authenticated.

#### Business Logic

- `ACTIVE` is returned only from a successful authenticated probe: the page shows the authenticated chat UI and a live composer.
- `AUTH_REQUIRED` is returned for any other failed probe: an expired login (`EXPIRED`), a launch failure (`LAUNCH_FAILURE`), or a timeout (`TIMEOUT`).
- The checker never reports `LIMITED` — limit detection is `ISessionLimitCheckerProtocol`'s concern (FR-Session-003).
- The underlying DOM predicates are the shared browser-session liveness, chat-page assertion, and in-page expiry banner utilities.
- The whole probe has a bounded `timeout_seconds` ceiling; a stalled launch is a login failure too. A cancelled probe gets a bounded grace window to tear down its own browser context (SA-4-01).

#### Edge Cases

- A rate-limited page that is still signed in is not a login failure and is reported `ACTIVE`.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A session naming the session path. |
| **Output** | A session health result carrying the login verdict (`ACTIVE` or `AUTH_REQUIRED`) and the reason. |
| **Protocol** | `ISessionLoginCheckerProtocol` — the session authentication probe seam. |
| **Method** | `check_session` — probes whether the session's chat page is still authenticated. |
| **Event** | `session_authenticated` — emitted when an `ACTIVE` verdict is reached. |
| **Error** | A probe that cannot open an authenticated page returns `AUTH_REQUIRED`, not an exception. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A login probe on a page whose composer is missing | `check_session` runs | It reports `AUTH_REQUIRED` with `EXPIRED` reason, never `LIMITED` |

#### Metric

| Target Metric | Value |
| --- | --- |
| Login-verdict accuracy | 100% |

### FR-Session-003: Detect a rate-limited session

**Description:**

Report whether the Qwen chat page behind a session is rate-limited.

#### Business Logic

- `ACTIVE` is returned when the page is healthy and shows no provider limit banner.
- `LIMITED` is returned when the limit banner is detected (reason `QUOTA`) or the probe timed out / could not get a reply (a missing reply is treated as a limit signal).
- The checker never reports `AUTH_REQUIRED` — login detection is `ISessionLoginCheckerProtocol`'s concern (FR-Session-002).
- A transient probe failure on a confirmed-LIMITED session keeps it LIMITED; it does not overwrite the quota evidence with invented data.
- An expired session that still shows the composer is still `ACTIVE` for the limit checker; expiry is the login checker's concern.
- Banner detection uses the rate-limit pattern constant from the shared taxonomy constants.

#### Edge Cases

- A page that is expired but still signed in is `ACTIVE` for the limit checker.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A session naming the session path. |
| **Output** | A session health result carrying the limit verdict (`ACTIVE` or `LIMITED`) and the reason. |
| **Protocol** | `ISessionLimitCheckerProtocol` — the session rate-limit probe seam. |
| **Method** | `check_session` — probes whether the session is rate-limited. |
| **Event** | `session_limited` — emitted when a `LIMITED` verdict is reached. |
| **Error** | A probe that times out or cannot get a reply returns `LIMITED`, not an exception. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A limit probe on a page with a rate-limit banner | `check_session` runs | It reports `LIMITED` with `QUOTA` reason, never `AUTH_REQUIRED` |

#### Metric

| Target Metric | Value |
| --- | --- |
| Limit-verdict accuracy | 100% |

### FR-Session-004: Rotate to the next healthy session

**Description:**

Select the next healthy session for a run, skipping already-tried and
rate-limited ones.

#### Business Logic

- `ACTIVE` is selected only from a successful authenticated probe (delegating to the limit checker).
- A rate-limited session is skipped.
- If no eligible session remains, return an explicit `no_eligible_session` outcome with `reason` and `recovery_action` BEFORE submitting; never submit through a known-LIMITED profile.
- Pool order is deterministic: the same pool state resolves the same session.
- Cross-account rotation on quota is permitted for authorized accounts only (see `docs/MULTI_ACCOUNT_ROTATION.md` policy gate).
- A CAPTCHA or provider access-control stop halts immediately; no bypass.
- The `rotate_sync` seam owns the event-loop handling so a sync caller never calls `asyncio.run` inline.

#### Edge Cases

- An empty pool returns `no_eligible_session` with `empty_pool`.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A rotation request naming the sessions already tried and the pool's health verdicts. |
| **Output** | The next session to use, or the `no_eligible_session` outcome with `reason` and `recovery_action`. |
| **Protocol** | `ISessionAggregate` — the session feature's aggregate door routing the rotate verb. |
| **Method** | `rotate`, `rotate_sync`, `get_next_session`. |
| **Event** | `session_rotated` — emitted when a healthy session is selected. |
| **Error** | A probe that cannot complete is treated as a limit signal, not an error; an empty or all-limited pool returns the reasoned `no_eligible_session` outcome. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A pool where every session is rate-limited | `rotate` runs | It returns `no_eligible_session` with `all_sessions_limited` |
| An empty pool | `rotate` runs | It returns `no_eligible_session` with `empty_pool` |

#### Metric

| Target Metric | Value |
| --- | --- |
| Rotation selection accuracy | 100% |

### FR-Session-005: Renew a stale auth session

**Description:**

Detect a stale auth session and renew it via the site's own refresh-token
flow, without forcing the user back to `session login`.

#### Business Logic

- The renewal cookie probe utilities (`is_refresh_token_valid`, `is_auth_session_expired`, `renewal_is_possible`) back this capability.
- A session whose profile no longer authenticates is first offered a transparent token renewal; only when renewal is impossible is it reported invalid (FR-Session-001).

#### Edge Cases

- A session whose refresh token is missing or expired is not renewable.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The application config and an optional session path. |
| **Output** | `True` when the session is healthy (either already, or after a successful renewal). |
| **Protocol** | `ISessionRenewalProtocol` — the transparent refresh-token renewal seam. |
| **Method** | `renew_session_if_stale`. |
| **Event** | `session_renewed` — emitted when a transparent renewal succeeds. |
| **Error** | Raises `AuthRequiredError` when renewal is impossible or fails — the caller must fall back to manual login. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A session whose profile no longer authenticates but whose refresh token is valid | `renew_session_if_stale` runs | The session is transparently renewed and reported healthy |

#### Metric

| Target Metric | Value |
| --- | --- |
| Renewal success rate on valid refresh tokens | 100% |

### FR-Session-006: Prepare a browser profile

**Description:**

Compute the mode→clone decision and hand the browser layer a plain prepared
Path.

#### Business Logic

- In login mode, the master session path is yielded directly so credentials persist.
- In any other mode, the master is cloned into an ephemeral temp dir so multiple browser processes can run concurrently without SingletonLock conflicts.
- The browser capability never clones the profile itself (AES201); this capability owns the decision.
- A missing master session path results in an empty (but valid) ephemeral dir.

#### Edge Cases

- A missing master session path yields an empty dir.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The application config. |
| **Output** | A context manager yielding the prepared session profile path. |
| **Protocol** | `IProfilePreparerProtocol` — the mode→clone decision and prepared-path seam. |
| **Method** | `prepare`. |
| **Event** | None — the prepared path is the observable result. |
| **Error** | A filesystem error surfaces an error naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A login-mode preparation | `prepare` runs | The master path is yielded directly |
| A standard-mode preparation | `prepare` runs | An ephemeral clone is yielded |

#### Metric

| Target Metric | Value |
| --- | --- |
| Mode→clone decision correctness | 100% |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `SessionOrchestrator` |
| Aggregate | `ISessionAggregate` |
| Method | `execute` |
| Request | `SessionRequest` — verbs `check_health`, `rotate`, `delete`, `login` |
| Response | `SessionResponse` — carries the valid flag, health verdicts, per-session reasons, and the reasoned `no_eligible_session` outcome |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
