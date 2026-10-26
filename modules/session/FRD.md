# SESSION Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The session feature owns the saved browser sessions: keeping the pool that
tracks them, checking which are still signed in, rotating to the next
healthy one when one is rate limited, renewing a stale auth session, and
deleting one safely. It owns one aggregate the surfaces call — the session
aggregate — which implements the session verbs, including the setup flow's
manual login.

Workspace initialization (XDG directories, `.qwen-web-arwaky` symlinks, SKILL.md
provisioning, `.gitignore` management) moved to the config feature
(`modules/config`), and the targeted run-cancel registry moved to the prompt
feature (`modules/prompt`). The session module now holds only the session
pool, health checking, rotation, renewal, deletion, and login.

## Functional Requirements

### FR-SESSION-001: Keep and rotate the session pool

- **Description**: Track the known sessions, register new ones, remove them,
and mark their health verdicts; pick the next session a run should use and
report reasoned health verdicts with sub-cause and recovery.
- **Input**: A rotation request naming the sessions already tried and the
pool's health verdicts.
- **Output**: The next session to use, or the reason none is available
(`no_eligible_session` with `reason` and `recovery_action`); reasoned
health verdicts with sub-cause and recovery.
- **Business Rules**:
  - The pool file is advisory. It is not the source of truth for which
  sessions exist. The session manager scans the session directory for
  registered session metadata and on-disk Chromium profiles.
  - The pool file is locked with an advisory lock
  (`sessions.json.lock`) during read-modify-write. A stale lock is
  detected and cleared before recovery.
  - Pool file writes are atomic (temp file + `os.replace` swap). A corrupt
  pool file is quarantined to `sessions.json.corrupt-<timestamp>` and
  rebuilt from disk.
  - Sessions discovered on disk but missing from the pool file are
  registered with `SessionStatus.AUTH_REQUIRED` (UNKNOWN remains a
  deprecated read-only alias for legacy pool files).
  - Session IDs are unique and never reused.
  - Pool order is deterministic: the same pool state resolves the same
  session.
  - A session whose profile no longer authenticates is first offered a
  transparent token renewal (while the refresh token is still valid); only
  when renewal is impossible is it reported invalid, so the operator
  chooses to re-login.
  - A session path that does not exist is reported invalid, not an error.
  - The session deletion target is always explicit; no wildcard or
  directory-wide deletion is permitted.
  - A saved Chromium profile is never deleted without a backup, unless the
  caller passes `force=True`.
  - A manual login registers the authenticated profile into the pool.
- **Edge Cases**: A session path that does not exist is reported invalid,
not an error.
- **Error Handling**: An inspection that cannot complete surfaces an error
naming the path.

### FR-SESSION-002: Authenticate the session

- **Description**: Report whether the Qwen chat page behind a session is
still authenticated.
- **Input**: A session naming the session path.
- **Output**: A session health result carrying the login verdict
(`ACTIVE` or `AUTH_REQUIRED`) and the reason.
- **Business Rules**:
  - `ACTIVE` is returned only from a successful authenticated probe: the
  page shows the authenticated chat UI and a live composer.
  - `AUTH_REQUIRED` is returned for any other failed probe: an expired
  login (`EXPIRED`), a launch failure (`LAUNCH_FAILURE`), or a timeout
  (`TIMEOUT`).
  - The checker never reports `LIMITED` — limit detection is
  `ISessionLimitCheckerProtocol`'s concern (FR-SESSION-003).
  - The underlying DOM predicates are the shared browser-session liveness,
  chat-page assertion, and in-page expiry banner utilities.
  - The whole probe has a bounded `timeout_seconds` ceiling; a stalled
  launch is a login failure too. A cancelled probe gets a bounded grace
  window to tear down its own browser context (SA-4-01).
- **Edge Cases**: A rate-limited page that is still signed in is not a
login failure and is reported `ACTIVE`.
- **Error Handling**: A probe that cannot open an authenticated page returns
`AUTH_REQUIRED`, not an exception.

### FR-SESSION-003: Detect a rate-limited session

- **Description**: Report whether the Qwen chat page behind a session is
rate-limited.
- **Input**: A session naming the session path.
- **Output**: A session health result carrying the limit verdict
(`ACTIVE` or `LIMITED`) and the reason.
- **Business Rules**:
  - `ACTIVE` is returned when the page is healthy and shows no provider
  limit banner.
  - `LIMITED` is returned when the limit banner is detected (reason
  `QUOTA`) or the probe timed out / could not get a reply (a missing
  reply is treated as a limit signal).
  - The checker never reports `AUTH_REQUIRED` — login detection is
  `ISessionLoginCheckerProtocol`'s concern (FR-SESSION-002).
  - A transient probe failure on a confirmed-LIMITED session keeps it
  LIMITED; it does not overwrite the quota evidence with invented data.
  - An expired session that still shows the composer is still `ACTIVE` for
  the limit checker; expiry is the login checker's concern.
  - Banner detection uses the rate-limit pattern constant from the shared
  taxonomy constants.
- **Edge Cases**: A page that is expired but still signed in is `ACTIVE`
for the limit checker.
- **Error Handling**: A probe that times out or cannot get a reply returns
`LIMITED`, not an exception.

### FR-SESSION-004: Rotate to the next healthy session

- **Description**: Select the next healthy session for a run, skipping
already-tried and rate-limited ones.
- **Input**: A rotation request naming the sessions already tried and the
pool's health verdicts.
- **Output**: The next session to use, or the reason none is available
(`no_eligible_session` with `reason` and `recovery_action`).
- **Business Rules**:
  - `ACTIVE` is selected only from a successful authenticated probe
  (delegating to the limit checker).
  - A rate-limited session is skipped.
  - If no eligible session remains, return an explicit `no_eligible_session`
  outcome with `reason` and `recovery_action` BEFORE submitting; never
  submit through a known-LIMITED profile.
  - Pool order is deterministic: the same pool state resolves the same
  session.
  - Cross-account rotation on quota is permitted for authorized accounts
  only (see `docs/MULTI_ACCOUNT_ROTATION.md` policy gate).
  - A CAPTCHA or provider access-control stop halts immediately; no bypass.
  - No promise a provider quota resets by a specific time.
  - The `rotate_sync` seam owns the event-loop handling so a sync caller
  never calls `asyncio.run` inline.
- **Edge Cases**: An empty pool returns `no_eligible_session` with
`empty_pool`.
- **Error Handling**: A probe that cannot complete is treated as a limit
signal, not an error.

### FR-SESSION-005: Renew a stale auth session

- **Description**: Detect a stale auth session and renew it via the site's
own refresh-token flow, without forcing the user back to
`session login`.
- **Input**: The application config and an optional session path.
- **Output**: `True` when the session is healthy (either already, or after
a successful renewal).
- **Business Rules**:
  - The renewal cookie probe utilities (`is_refresh_token_valid`,
  `is_auth_session_expired`, `renewal_is_possible`) back this capability.
  - A session whose profile no longer authenticates is first offered a
  transparent token renewal; only when renewal is impossible is it
  reported invalid (FR-SESSION-001).
- **Edge Cases**: A session whose refresh token is missing or expired is
not renewable.
- **Error Handling**: Raises `AuthRequiredError` when renewal is impossible
or fails — the caller must fall back to manual login.

### FR-SESSION-006: Prepare a browser profile

- **Description**: Compute the mode→clone decision and hand the browser
layer a plain prepared Path.
- **Input**: The application config.
- **Output**: A context manager yielding the prepared session profile path.
- **Business Rules**:
  - In login mode, the master session path is yielded directly so
  credentials persist.
  - In any other mode, the master is cloned into an ephemeral temp dir so
  multiple browser processes can run concurrently without SingletonLock
  conflicts.
  - The browser capability never clones the profile itself (AES201); this
  capability owns the decision.
  - A missing master session path results in an empty (but valid) ephemeral
  dir.
- **Edge Cases**: A missing master session path yields an empty dir.
- **Error Handling**: A filesystem error surfaces an error naming the path.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `load_pool` | none | SessionPool | file error | none | Read the tracked session pool, quarantining a corrupt file and rebuilding from disk. |
| `save_pool` | SessionPool | None | file error | none | Persist the pool atomically (temp file + `os.replace` swap). |
| `add_session` | name, profile path | SessionInfo | file error | none | Add one session with a unique ID. |
| `remove_session` | session ID | bool | file error | none | Remove one session from the pool. |
| `get_session_by_name` | name | SessionInfo or None | none | none | Read the pool entry registered under a name. |
| `delete_session_profile` | profile path, force | bool | QwenCliError | none | Remove a saved Chromium profile; refused without a backup unless forced (FR-SESSION-001). |
| `mark_healthy` / `mark_limited` / `mark_auth_required` | session ID, optional reason | None | file error | none | Mark pool entry status (FR-SESSION-001). |
| `check_session` | SessionInfo | SessionHealthResult (ACTIVE or AUTH_REQUIRED) | none | none | Probe whether the session is still authenticated (FR-SESSION-002). |
| `check_session` | SessionInfo | SessionHealthResult (ACTIVE or LIMITED) | none | none | Probe whether the session is rate-limited (FR-SESSION-003). |
| `rotate` | RotatorRequest | RotatorResponse | none | none | Select the next healthy session, skipping already-tried and rate-limited (FR-SESSION-004). |
| `rotate_sync` | RotatorRequest | RotatorResponse | none | none | Synchronous wrapper that owns the event loop. |
| `get_next_session` | none | SessionInfo or None | none | none | Pick the next healthy session by round-robin order. |
| `renew_session_if_stale` | AppConfig, optional session path | bool | AuthRequiredError | none | Transparent refresh-token renewal when the auth session is stale (FR-SESSION-005). |
| `prepare` | AppConfig | context manager yielding Path | file error | none | Mode→clone decision: login yields master path; otherwise yields an ephemeral clone (FR-SESSION-006). |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | SessionRequest | SessionResponse | none | none | Single entry point over the session feature; routes on `request.verb`. |

#### Verb Contracts

- **check_health** — runs the login checker and the limit checker over every
pooled session, then writes the synthesized verdict back to the pool
(`mark_healthy` / `mark_limited` / `mark_auth_required`). Returns a
session response carrying the valid flag, the health verdicts, and the
per-session reasons.
- **rotate** — selects the next healthy session from the pool, skipping
already-tried and rate-limited ones, and returns it or a reasoned
`no_eligible_session` outcome.
- **delete** — removes a session and its Chromium profile; refused without a
backup unless forced.
- **login** — registers the authenticated profile into the pool.

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Browser capability | out | The login and limit checkers drive the browser through the lifecycle seam (`health_probe_page`); the profile preparer hands the browser a prepared Path. | authentication error -> session reported invalid |
| Prompt capability | out | The session orchestrator passes the resolved session to the prompt feature for prompt assembly. | none -> prompt assembly blocked |
| Config capability | out | The session orchestrator reads `AppConfig` for session directory, output path, and profile mode. | file error -> session path unresolvable |
| Shared utilities | out | The checkers rely on the shared browser-session liveness utilities; the renewal capability relies on the renewal cookie probe utilities. | probe failure -> session reported invalid |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Pool operation cost | O(n) over registered session count | session count bound check |
| Pool file concurrency | advisory lock during read-modify-write | lock presence check |
| Profile deletion safety | never deleted without backup unless `force=True` | backup guard check |

## Test Scenarios

- A pool file is missing or corrupt; the session manager rebuilds the pool
from disk (FR-SESSION-001).
- A session is added to the pool; it is registered with a unique ID and
persisted (FR-SESSION-001).
- A session is removed from the pool; the pool is persisted and the session
is no longer returned (FR-SESSION-001).
- A session's profile no longer authenticates; it is first offered a
transparent token renewal (FR-SESSION-005); only when renewal is
impossible is it reported invalid (FR-SESSION-001).
- A login probe on a page whose composer is missing reports `AUTH_REQUIRED`
with `EXPIRED` reason, never `LIMITED` (FR-SESSION-002).
- A limit probe on a page with a rate-limit banner reports `LIMITED` with
`QUOTA` reason, never `AUTH_REQUIRED` (FR-SESSION-003).
- A limit probe that times out reports `LIMITED`, not `AUTH_REQUIRED`
(FR-SESSION-003).
- A transient probe failure on a confirmed-LIMITED session keeps it LIMITED
(FR-SESSION-003).
- Rotation on a pool where every session is rate-limited returns
`no_eligible_session` with `all_sessions_limited` (FR-SESSION-004).
- Rotation on an empty pool returns `no_eligible_session` with `empty_pool`
(FR-SESSION-004).
- A session whose profile no longer authenticates is transparently renewed
first (FR-SESSION-005); only when renewal is impossible is it reported
invalid (FR-SESSION-001).
- A login mode profile preparation yields the master path; a standard mode
preparation yields an ephemeral clone (FR-SESSION-006).

## Assumptions & Constraints

- The session directory is under the user's control; the session manager
must not assume it exists.
- The session pool file is advisory; the on-disk profiles are the source of
truth.
- The session manager must not assume a session's profile directory exists
when it is registered.
- The two checkers are strictly separated — the login checker never produces
`LIMITED` and the limit checker never produces `AUTH_REQUIRED`; a combined
verdict is only ever synthesized by the agent orchestrator's
`_run_pool_checks` helper, never by a capability.
- The session module does not own the browser capability; it drives it
through the `IBrowserLifecycleProtocol` seam.

## Glossary

- **Session pool**: The tracked list of saved browser sessions and their
health verdicts (FR-SESSION-001).
- **Login checker**: Probes whether a session's chat page is still
authenticated; returns ACTIVE or AUTH_REQUIRED (FR-SESSION-002).
- **Limit checker**: Probes whether a session's chat page is rate-limited;
returns ACTIVE or LIMITED (FR-SESSION-003).
- **Rotation**: Picking the next healthy session for a run, skipping
rate-limited ones (FR-SESSION-004).
- **Renewal**: Transparent refresh-token exchange when the auth session is
stale (FR-SESSION-005).
- **Profile preparation**: The mode→clone decision that hands the browser
layer a prepared Path (FR-SESSION-006).
- **Backup guard**: The refusal that blocks deleting a master profile
without a written backup (FR-SESSION-001).
