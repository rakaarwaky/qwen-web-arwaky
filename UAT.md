# User Acceptance Tests

These scenarios cover the supported personas in `PRD.md`. Run them from a clean workspace with a valid Qwen Web session.

## Interactive operator

Start `qwen-web-arwaky`, initialize a slot with a Markdown prompt, and press Enter. The slot must show progress, preserve the output file, and return to an idle state after completion. Press `?` and verify that `alt+left` and `alt+right` are documented.

## Automation operator

Run `qwen-web-arwaky prompt direct -t "Summarize this" -o output.md --headless`. The command must return a success envelope and write the response to `output.md`.

## MCP client

Start `qwen-web-mcp`, list tools, and invoke `init`, `check_session`, and `list_jobs`. A prompt file outside `QWEN_WORKSPACE_ROOT` must be rejected with `PATH_OUTSIDE_WORKSPACE`.

## Recovery operator

Run `qwen-web-arwaky doctor` and `qwen-web-arwaky update --check`. Diagnostics must be readable without mutating the workspace.

## Manual verification scenarios

The following scenarios need a live human at the browser (CAPTCHA, 2FA, or a
visual confirmation step), so they are not automated. Run them from a clean
workspace and record the outcome in the release notes.

| ID | Scenario | Expected evidence |
|---|---|---|
| UAT-MAN-001 | `qwen-web-arwaky session login --name <name>` interactive round-trip | A headed browser opens at `chat.qwen.ai`; after a manual login the window closes, the session is registered in the pool, and the "Add another session?" re-prompt loops correctly (answering `y` asks for another name; `N` exits 0). Confirm with `qwen-web-arwaky session list` and `session status`. |
| UAT-MAN-002 | `qwen-web-arwaky session remove <name>` destructive removal | The pool entry and the Chromium profile directory are removed; `--keep-profile` leaves the profile on disk. Verify with `session list` and the profile directory. |
| UAT-MAN-003 | `qwen-web-arwaky doctor --deep --json` | The heavy Playwright probe runs after a stderr notice; the JSON report's checks carry `severity: "ok"` for passing records. |

## BA verification scenarios

The following deterministic scenarios are required for release sign-off:

| ID | Scenario | Expected evidence |
|---|---|---|
| UAT-BA-004 | Compile an attachment above 100 MiB | Validation fails before browser interaction with the size limit. |
| UAT-BA-005 | Inspect `metrics.json` after terminal outcomes | `total_executions`, `successful_executions`, and `success_rate` are persisted. |
| UAT-BA-006 | Submit and age terminal/stale jobs | Cleanup removes terminal jobs after 24 hours and incomplete jobs after 7 days. |
| UAT-BA-007 | Run MCP destructive session action without confirmation | The action is rejected and the session remains intact. |
| UAT-BA-008 | Run async job lifecycle | Submit, poll, complete, and retrieve output are all represented in JSON. |


## Isolated UAT setup

