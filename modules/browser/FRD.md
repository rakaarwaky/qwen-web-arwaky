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

### FR-BROWSER-001: Launch an authenticated browser context

- **Description**: Open the persistent Chromium context over the saved session profile and yield its context manager.
- **Input**: A validated runtime configuration carrying the session path, headless flag, sandbox verdict, and browser binary preference.
- **Output**: A context manager yielding the live browser context for the lifetime of one run.
- **Business Rules**:
  - The session directory is created with owner-only permissions; a pre-existing directory with wider permissions is repaired before launch.
  - Stale Chromium lock files left by a killed run are removed before launch so a clean run is not blocked by a dead process.
  - The configured model is resolved before the first page is handed over.
- **Edge Cases**: A launch that fails after retries surfaces a browser-launch error naming the reason; a sandbox the host cannot provide falls back to the sandbox-disabled launch only when the configuration allows it.
- **Error Handling**: Browser-launch errors carry the host capability that failed; session-directory permission failures surface as a file error naming the path.

### FR-BROWSER-002: Navigate to the chat and prove authentication

- **Description**: Take a page to the chat and prove the saved session is still signed in.
- **Input**: A live page and the lifecycle emitter that records progress events.
- **Output**: A page positioned on an authenticated chat, or an authentication error.
- **Business Rules**:
  - Authentication is proven before the page is handed to a caller; no caller may receive an unauthenticated page.
  - A page still loading is tolerated while it exposes the authenticated UI.
- **Edge Cases**: A page redirected to a login URL or showing a login form raises an authentication error rather than returning an unusable page.
- **Error Handling**: An authentication error names the login path so the caller can route the operator to the setup verb.

### FR-BROWSER-003: Select the pinned model

- **Description**: Make the chat use the model the run configuration requests.
- **Input**: A live page and the run's target model.
- **Output**: A boolean reporting whether the requested model is now active.
- **Business Rules**:
  - A model requested per run is resolved without mutating shared state, so concurrent runs keep their own override.
  - A picker that does not expose the requested model falls back to the first model it offers and records a warning rather than aborting the run.
- **Edge Cases**: A picker that never becomes ready falls back through the configured retry budget before reporting failure.
- **Error Handling**: A model switch that cannot complete surfaces a model-switch error naming the requested and active model.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `browser_session` | runtime configuration | context manager over the live context | browser-launch error | launch progress | Open the persistent authenticated context. |
| `navigate_to_chat` | page, lifecycle emitter | page on an authenticated chat | authentication error | page loaded | Take the page to the chat. |
| `check_auth` | page | none; raises on failure | authentication error | none | Assert the page is an authenticated chat. |
| `check_session` | page | boolean readiness verdict | none | none | Report whether the page is ready for use. |

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
- An event-loop-hosting worker thread gets an isolated event loop so the sync browser API never raises.

## Assumptions & Constraints

- The session profile directory is the only place live login cookies exist; it is never written to a shared path.
- A browser binary discovered outside the managed build must pass an ownership and permission check before it is trusted, because it would receive those cookies.
- The chat DOM selectors the adapter matches are pinned by regression tests; changing them is a deliberate, reviewed change.

## Glossary

- **Persistent context**: The Chromium profile that keeps cookies between runs.
- **Authenticator probe**: The check that proves a page shows a signed-in chat rather than a login form.
- **Model picker**: The in-page control that lists the models the account can use.
