# BROWSER Functional Requirements Document

## Feature Overview

The browser feature owns every Chromium interaction the pipeline depends on.
It launches the persistent authenticated context, navigates to the chat,
proves the saved session is still signed in, and pins the requested model.
Surfaces never touch a page; the prompt, session, and setup orchestrators
call `IBrowserAggregate.open_session` and receive a page already proven
usable. The orchestrator composes four capabilities — lifecycle, navigation,
model policy, and diagnostics — behind the aggregate door.

## Functional Requirements

### FR-Browser-003: Select, verify, and probe the target model

**Description:**

Resolve the configured target model for the run, drive the in-page picker to
that model when it is offered, verify the active model matches the target,
and fall back to the first available model when it does not — the product
policy about which model a run targets, kept out of the browser adapter so
the DOM mechanics stay in one place.

#### Business Logic

- The configured target model is resolved per run (a contextvar bound once per browser context launch), so concurrent runs keep their own override without mutating shared state.
- A picker that does not expose the requested model falls back to the first model it offers and records a warning rather than aborting the run (issue #283 AC-2, issue #374).
- A verification retry budget is bounded; a slow picker hydrating must not fail the pipeline (issue #283).
- Liveness probes never raise: an unreadable or still-loading page reports False instead of an error.
- Authentication combines the URL check, the login-form check, and the in-page expiry banner check.

#### Edge Cases

- A picker that never becomes ready falls back through the retry budget before reporting a model-switch error; an unreadable model label raises a model-switch error naming the trigger selector; a page whose DOM is mid-hydration reports False rather than a spurious authentication error.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The live Playwright page and the lifecycle emitter that records the model-verified event. |
| **Output** | `select_model` returns the chosen model label; `verify_model` returns a boolean verdict on whether the expected label is active. |
| **Protocol** | `IBrowserModelPolicyProtocol` — the in-page model picker and verification seam. |
| **Method** | `select_model`, `verify_model`, `verify_default_model`, `select_first_available_model`, `wait_for_picker_ready`, `retry_default_model_selection`, `get_model_trigger`, `try_set_as_default`, `ensure_default_model`. |
| **Event** | `model_verified` — recorded by the lifecycle emitter when the picker lands on a model. |
| **Error** | A model switch that cannot complete surfaces a model-switch error naming the requested and active model; best-effort selection failures are logged and swallowed so the prompt pipeline is never blocked; browser errors during the probe surface as an authentication error naming the reason. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A picker that does not expose the requested model | The model policy falls back | The first offered model is chosen and a warning is recorded |
| A page whose DOM is still hydrating | A liveness probe runs | The probe reports False rather than raising |

#### Metric

| Target Metric | Value |
| --- | --- |
| Model-verification pass rate | 100% |

### FR-Browser-004: Launch and tear down the persistent Chromium context

**Description:**

Launch the persistent Chromium context over a saved or prepared session
profile, wire the asset-abort and diagnostic hooks, and tear the process
group down on exit — the one capability that turns a validated runtime
configuration into a live browser context.

#### Business Logic

- The session directory is created with owner-only permissions; a pre-existing directory with wider permissions is repaired before launch.
- Stale Chromium lock files left by a killed run are removed before launch so a clean run is not blocked by a dead process.
- A launch that fails after retries surfaces a browser-launch error naming the reason.
- A sandbox the host cannot provide falls back to the sandbox-disabled launch only when the configuration allows it.

#### Edge Cases

- A context close that raises is best-effort and never masks the caller's domain failure.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A validated runtime configuration carrying the session path, headless flag, sandbox verdict, and browser binary preference, plus an optional prepared session profile path and executable path. |
| **Output** | A context manager yielding the live browser context; exiting tears the browser process group down so a raising caller cannot leak a process. |
| **Protocol** | `IBrowserLifecycleProtocol` — the context launch and teardown seam. |
| **Method** | `browser_session`, `health_probe_page`, `renew_session`, `open_login_page`. |
| **Event** | `launch_progress` — emitted as the context comes up and tears down. |
| **Error** | Browser-launch errors carry the host capability that failed; session-directory permission failures surface as a file error naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A pre-existing session directory with world-readable permissions | The context launches | The directory is repaired to owner-only before launch |
| A caller body that raises inside the context | Teardown runs | The process group is torn down without masking the domain failure |

#### Metric

| Target Metric | Value |
| --- | --- |
| Launch success rate after stale-lock cleanup | 100% |

### FR-Browser-005: Navigate the page to the chat and reset it to a clean state

**Description:**

Drive the browser page to the chat URL, assert authentication, reset to a
clean conversation, and open the manual-login window — pure browser
mechanics with no model-selection policy and no profile-cloning.

#### Business Logic

- Navigation uses a bounded retry budget with backoff so a transient DNS or network stall does not abort the run.
- Authentication is proven before the page is handed to a caller; no caller may receive an unauthenticated page.
- A page redirected to a login URL or showing a login form raises an authentication error.

#### Edge Cases

- A page that is still loading is tolerated while it exposes the authenticated UI; the `open_login_page` wrapper performs no model selection.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The live Playwright page, the lifecycle emitter, and the runtime configuration for `open_login_page`. |
| **Output** | The page positioned on the authenticated chat with a clean conversation, or the raised authentication error. |
| **Protocol** | `IBrowserNavigationProtocol` — the chat navigation, authentication assertion, and reset seam. |
| **Method** | `navigate_to_chat`, `check_auth`, `reset_page`. |
| **Event** | `page_loaded` and `network_reconnecting` — recorded by the lifecycle emitter. |
| **Error** | An authentication error names the login path so the caller can route the operator to the setup verb; navigation timeouts surface as browser errors. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A page redirected to a login URL | The navigation asserts authentication | An authentication error is raised instead of yielding the page |
| A fresh page on the chat URL | `reset_page` runs | The conversation is reset to a clean state |

#### Metric

| Target Metric | Value |
| --- | --- |
| Authentication-assert pass rate | 100% |

### FR-Browser-006: Wire per-context and per-page diagnostics

**Description:**

Attach network, console, and URL-scrubbing diagnostics at both the context
level (asset-abort route, page-creation hook) and the per-page level
(request/response/console listeners), demoting third-party noise so it never
reaches the operator log.

#### Business Logic

- Diagnostics cover both levels: the context-level asset-abort route plus the page-creation hook that attaches per-page listeners to new and existing pages.
- Third-party tracking/CDN pixel failures and console noise are demoted to DEBUG so they never reach the operator log or the TUI log panel.
- URLs are scrubbed before logging so credentials and query tokens never exfiltrate into the log.

#### Edge Cases

- A context close that fails is best-effort and never masks the caller's domain failure; a failed diagnostic wire-up is logged and swallowed so it cannot block the run.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The live browser context. |
| **Output** | None; diagnostics are attached to the context and its pages (the context-level asset-abort route, the page-creation hook, per-page request/console/response listeners, URL scrubbing, and third-party noise demotion). |
| **Protocol** | `IBrowserDiagnosticsProtocol` — the per-context and per-page observability seam. |
| **Method** | `wire_diagnostics`. |
| **Event** | None — diagnostics are observational; a failed wire-up is logged and swallowed. |
| **Error** | None — a failed diagnostic wire-up is logged and swallowed so it cannot block the run. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A third-party tracking pixel that fails | Diagnostics run | The noise is demoted to DEBUG and never reaches the operator log |
| A URL carrying a query token | Diagnostics scrub the URL | The token never exfiltrates into the log |

#### Metric

| Target Metric | Value |
| --- | --- |
| URL-scrub coverage | 100% |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `BrowserOrchestrator` |
| Aggregate | `IBrowserAggregate` |
| Method | `open_session` |
| Request | `AppConfig` |
| Response | Context manager yielding a proven-authenticated `Page` |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
