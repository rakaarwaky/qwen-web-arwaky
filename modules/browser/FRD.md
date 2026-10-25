# BROWSER Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The browser feature owns every Chromium interaction the pipeline depends on:
it launches the persistent authenticated context, navigates to the chat,
proves the saved session is still signed in, and pins the requested model.
Surfaces never touch a page; the prompt, session, and setup orchestrators
call the aggregate and receive a page already proven usable.

## Functional Requirements

### FR-BROWSER-001: Open an authenticated, model-pinned chat session

- **Description**: Open the persistent Chromium context over the saved session profile, take its page to the chat, prove the saved session is still signed in, and pin the model the run requested — the one capability that turns a runtime configuration into a page a caller can drive.
- **Input**: A validated runtime configuration carrying the session path, headless flag, sandbox verdict, browser binary preference, and target model, plus the lifecycle emitter that records progress events.
- **Output**: A context manager yielding the live browser context whose page is already positioned on an authenticated chat running the requested model, or the error that stopped it.
- **Business Rules**:
  - The session directory is created with owner-only permissions; a pre-existing directory with wider permissions is repaired before launch.
  - Stale Chromium lock files left by a killed run are removed before launch so a clean run is not blocked by a dead process.
  - Authentication is proven before the page is handed to a caller; no caller may receive an unauthenticated page.
  - A page still loading is tolerated while it exposes the authenticated UI.
  - The configured model is resolved before the first page is handed over, without mutating shared state, so concurrent runs keep their own override.
  - A picker that does not expose the requested model falls back to the first model it offers and records a warning rather than aborting the run.
- **Edge Cases**: A launch that fails after retries surfaces a browser-launch error naming the reason; a sandbox the host cannot provide falls back to the sandbox-disabled launch only when the configuration allows it; a page redirected to a login URL or showing a login form raises an authentication error rather than yielding an unusable page; a picker that never becomes ready falls back through the configured retry budget before reporting failure.
- **Error Handling**: Browser-launch errors carry the host capability that failed; session-directory permission failures surface as a file error naming the path; an authentication error names the login path so the caller can route the operator to the setup verb; a model switch that cannot complete surfaces a model-switch error naming the requested and active model.

### FR-BROWSER-002: Probe session liveness and authentication

- **Description**: Bind one page to a session probe that reports whether the chat UI is alive and asserts the saved session is still authenticated, and drive model selection/verification policy — the checks and policies every pipeline run depends on before it dispatches a prompt.
- **Input**: The live Playwright page to probe.
- **Output**: A boolean liveness verdict from `is_alive`, and `check_auth` raising an authentication error when the page is a login or guest view, shows a login form, or an in-page session-expiry banner.
- **Business Rules**:
  - Liveness never raises: an unreadable or still-loading page reports False instead of an error.
  - Authentication combines the URL check, the login-form check, and the in-page expiry banner check.
  - A page that is still hydrating is tolerated by `check_auth` while it exposes the authenticated UI.
- **Edge Cases**: A page whose DOM is mid-hydration reports False rather than a spurious authentication error; an in-page expiry notice on the chat URL raises the authentication error naming the re-login verb.
- **Error Handling**: An authentication error names the login path so the caller can route the operator to the setup verb; browser errors during the probe surface as an authentication error naming the reason.

### FR-BROWSER-003: Select and verify the target model (issue #283/#374 fallback rules)

- **Description**: Resolve the configured target model for the run, drive the in-page picker to that model when it is offered, verify the active model matches the target, and fall back to the first available model when it does not — the product policy about which model a run targets, kept out of the browser adapter so the DOM mechanics stay in one place.
- **Input**: The live Playwright page and the lifecycle emitter that records the model-verified event.
- **Output**: `select_model` returns the chosen model label; `verify_model` returns a boolean verdict on whether the expected label is active.
- **Business Rules**:
  - The configured target model is resolved per run (a contextvar bound once per browser context launch), so concurrent runs keep their own override without mutating shared state.
  - A picker that does not expose the requested model falls back to the first model it offers and records a warning rather than aborting the run (issue #283 AC-2, issue #374).
  - A verification retry budget is bounded; a slow picker hydrating must not fail the pipeline (issue #283).
- **Edge Cases**: A picker that never becomes ready falls back through the retry budget before reporting a model-switch error; an unreadable model label raises a model-switch error naming the trigger selector.
- **Error Handling**: A model switch that cannot complete surfaces a model-switch error naming the requested and active model; best-effort selection failures are logged and swallowed so the prompt pipeline is never blocked.

### FR-BROWSER-004: Launch and tear down the persistent Chromium context

- **Description**: Launch the persistent Chromium context over a saved or prepared session profile, wire the asset-abort and diagnostic hooks, and tear the process group down on exit — the one capability that turns a validated runtime configuration into a live browser context.
- **Input**: A validated runtime configuration carrying the session path, headless flag, sandbox verdict, and browser binary preference, plus an optional prepared session profile path and executable path.
- **Output**: A context manager yielding the live browser context; exiting tears the browser process group down so a raising caller cannot leak a process.
- **Business Rules**:
  - The session directory is created with owner-only permissions; a pre-existing directory with wider permissions is repaired before launch.
  - Stale Chromium lock files left by a killed run are removed before launch so a clean run is not blocked by a dead process.
  - A launch that fails after retries surfaces a browser-launch error naming the reason.
  - A sandbox the host cannot provide falls back to the sandbox-disabled launch only when the configuration allows it.
- **Edge Cases**: A context close that raises is best-effort and never masks the caller's domain failure.
- **Error Handling**: Browser-launch errors carry the host capability that failed; session-directory permission failures surface as a file error naming the path.

### FR-BROWSER-005: Navigate the page to the chat and reset it to a clean state

- **Description**: Drive the browser page to the chat URL, assert authentication, reset to a clean conversation, and open the manual-login window — pure browser mechanics with no model-selection policy and no profile-cloning.
- **Input**: The live Playwright page, the lifecycle emitter, and the runtime configuration for `open_login_page`.
- **Output**: The page positioned on the authenticated chat with a clean conversation, or the raised authentication error.
- **Business Rules**:
  - Navigation uses a bounded retry budget with backoff so a transient DNS or network stall does not abort the run.
  - Authentication is proven before the page is handed to a caller; no caller may receive an unauthenticated page.
  - A page redirected to a login URL or showing a login form raises an authentication error.
- **Edge Cases**: A page that is still loading is tolerated while it exposes the authenticated UI; the `open_login_page` wrapper performs no model selection.
- **Error Handling**: An authentication error names the login path so the caller can route the operator to the setup verb; navigation timeouts surface as browser errors.

### FR-BROWSER-006: Wire per-context and per-page diagnostics

- **Description**: Attach network, console, and URL-scrubbing diagnostics at both the context level (asset-abort route, page-creation hook) and the per-page level (request/response/console listeners), demoting third-party noise so it never reaches the operator log.
- **Input**: The live browser context.
- **Output**: None; diagnostics are attached to the context and its pages (the context-level asset-abort route, the page-creation hook, per-page request/console/response listeners, URL scrubbing, and third-party noise demotion).
- **Business Rules**:
  - Diagnostics cover both levels: the context-level asset-abort route plus the page-creation hook that attaches per-page listeners to new and existing pages.
  - Third-party tracking/CDN pixel failures and console noise are demoted to DEBUG so they never reach the operator log or the TUI log panel.
  - URLs are scrubbed before logging so credentials and query tokens never exfiltrate into the log.
- **Edge Cases**: A context close that fails is best-effort and never masks the caller's domain failure.
- **Error Handling**: None — diagnostics are observational; a failed diagnostic wire-up is logged and swallowed so it cannot block the run.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `browser_session` | runtime configuration, optional prepared session path and executable path | context manager over the live context | browser-launch error | launch progress | Open the persistent authenticated context. |
| `navigate_to_chat` | page, lifecycle emitter | page on an authenticated chat | authentication error | page loaded | Take the page to the chat. |
| `check_auth` | page | none; raises on failure | authentication error | none | Assert the page is an authenticated chat. |
| `check_session` | page | boolean readiness verdict | none | none | Report whether the page is ready for use. |
| `detect_session_expired` | page | boolean verdict when the in-page expiry banner shows | none | none | Re-run the banner scan against the current page state. |
| `health_probe_page` | runtime configuration, optional prepared session path and executable path | context manager yielding one ready page | authentication error | none | Open one ephemeral health-probe page. |
| `renew_session` | runtime configuration, optional prepared session path and executable path | none; raises on failure | authentication error | none | Renew the master-profile session in place. |
| `reset_page` | page, lifecycle emitter | a clean chat state | none | network reconnecting | Navigate back to the chat and emit the reset event. |
| `open_login_page` | runtime configuration | context manager yielding one fresh page on the chat URL | browser-launch error | none | Open the manual-login window (FR-BROWSER-005). |
| `wire_diagnostics` | live browser context | none | none | none | Attach asset-abort route, page-creation hook, and per-page listeners (FR-BROWSER-006). |
| `select_model` | page, lifecycle emitter | the chosen model label | model-switch error | model verified | Select the run's target model (FR-BROWSER-003). |
| `verify_model` | page, expected label | boolean verdict | none | none | Verify the active model (FR-BROWSER-003). |
| `is_alive` | none (bound page) | boolean liveness verdict | none | none | Report whether the session is stable and the chat UI is responsive (FR-BROWSER-002). |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `open_session` | runtime configuration | context manager yielding a proven-authenticated page | authentication error, browser-launch error | page loaded, login verified, model verified | Single entry point callers use to obtain a usable page. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Prompt orchestrators | out | Obtain a page per prompt run | authentication error -> caller routes to setup |
| Session orchestrators | out | Validate or delete a stored session | authentication error -> session reported invalid |
| Setup orchestrators | out | Run the manual login sequence | authentication error -> manual login retried |
| Swarm orchestrators | out | One page per fan-out browser | browser-launch error -> that fan-out leg fails |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Session directory permissions | owner-only (`0700`) on every launch | mode check after context creation |
| Navigation retry budget | bounded retries with backoff before failing | launch attempt counter |
| Stale lock cleanup | lock files removed before every launch | lock presence check after cleanup |

## Test Scenarios

- A launch hands the caller a page that is already authenticated, and tears the context down when the caller's body raises.
- A page redirected to a login URL raises an authentication error instead of yielding.
- A requested model the picker does not expose falls back to the first offered model and records a warning.
- A pre-existing session directory with world-readable permissions is repaired before launch.
- A session directory owned by a different uid than the launching user is detected before launch; when the launcher has write access it is repaired in place, otherwise launch is refused with reason code `session_dir_cross_user` before any browser process starts (BROWSER-03).
- An event-loop-hosting worker thread gets an isolated event loop so the sync browser API never raises.

## Assumptions & Constraints

- The session profile directory is the only place live login cookies exist; it is never written to a shared path.
- A browser binary discovered outside the managed build must pass an ownership and permission check before it is trusted, because it would receive those cookies.
- The chat DOM selectors the adapter matches are pinned by regression tests; changing them is a deliberate, reviewed change.

## Glossary

- **Persistent context**: The Chromium profile that keeps cookies between runs.
- **Authenticator probe**: The check that proves a page shows a signed-in chat rather than a login form.
- **Model picker**: The in-page control that lists the models the account can use.
