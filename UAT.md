# User Acceptance Tests

These scenarios cover the supported personas in `PRD.md`. Run them from a clean workspace with a valid Qwen Web session.

## Interactive operator

Start `qwen-web-arwaky`, initialize a slot with a Markdown prompt, and press Enter. The slot must show progress, preserve the output file, and return to an idle state after completion. Press `?` and verify that `alt+left` and `alt+right` are documented.

## Automation operator

Run `qwen-web-arwaky prompt-direct -t "Summarize this" -o output.md --headless`. The command must return a success envelope and write the response to `output.md`.

## MCP client

Start `qwen-web-mcp`, list tools, and invoke `init`, `check_session`, and `list_jobs`. A prompt file outside `QWEN_WORKSPACE_ROOT` must be rejected with `PATH_OUTSIDE_WORKSPACE`.

## Recovery operator

Run `qwen-web-arwaky doctor` and `qwen-web-arwaky update --check`. Diagnostics must be readable without mutating the workspace.

## BA verification scenarios

The following deterministic scenarios are required for release sign-off:

| ID | Scenario | Expected evidence |
|---|---|---|
| UAT-BA-001 | Run `batch` with two Markdown prompts | Each file moves through `.processing` to `done`; output files exist. |
| UAT-BA-002 | Run `batch` with a failing prompt | The file is moved to `failed` and the other files continue. |
| UAT-BA-003 | Run `watch --interval 1` and add a prompt | The new prompt is picked up without restarting the process. |
| UAT-BA-004 | Compile an attachment above 100 MiB | Validation fails before browser interaction with the size limit. |
| UAT-BA-005 | Inspect `metrics.json` after terminal outcomes | `total_executions`, `successful_executions`, and `success_rate` are persisted. |
| UAT-BA-006 | Submit and age terminal/stale jobs | Cleanup removes terminal jobs after 24 hours and incomplete jobs after 7 days. |
| UAT-BA-007 | Run MCP destructive session action without confirmation | The action is rejected and the session remains intact. |
| UAT-BA-008 | Run async job lifecycle | Submit, poll, complete, and retrieve output are all represented in JSON. |


## Isolated UAT setup

Run `tests/uat/setup.sh` before deterministic UAT. It creates isolated input, processing, done, failed, output, and session directories without performing live authentication. Browser-backed scenarios may supply a session separately.
