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

The deterministic scenarios below and goal-linked acceptance exercises for Goals 1–5 are required for release sign-off; each records its commit, preconditions, measured result, evidence and reviewer disposition.

| ID | Scenario | Expected evidence |
|---|---|---|
| UAT-BA-004 | Compile an attachment above 100 MiB | Validation fails before browser interaction with the size limit. |
| UAT-BA-005 | Inspect `metrics.json` after terminal outcomes | `total_executions`, `successful_executions`, and `success_rate` are persisted. |
| UAT-BA-006 | Submit and age terminal/stale jobs | Cleanup removes terminal jobs after 24 hours and incomplete jobs after 7 days. |
| UAT-BA-007 | Run MCP destructive session action without confirmation | The action is rejected and the session remains intact. |
| UAT-BA-008 | Run async job lifecycle | Submit, poll, complete, and retrieve output are all represented in JSON. |
| UAT-BA-009 – UAT-BA-013 | Goal-linked acceptance exercises for Goals 1–5 | See the Goal-to-Scenario Evidence Matrix below for preconditions, steps, oracles, thresholds, and recorded evidence. |
| UAT-BA-014 | Attachment boundary matrix (BA-3-001) | Zero bytes, exact max, max+1, unreadable, unsupported format, type/content mismatch — each fails at pre-flight with a stable reason and no provider submission. |
| UAT-BA-015 | Session health verdict classification (BA-2-001) | ACTIVE, LIMITED, AUTH_REQUIRED verdicts carry the correct reason and recovery action; a transient failure on a LIMITED session leaves it LIMITED. |
| UAT-BA-016 | Rotation no_eligible_session outcomes (BA-2-002) | Empty pool, single-limited, all-limited, excluded-all, and mixed pools each return the explicit outcome field; no submission through a known-LIMITED profile. |

## Goal-to-Scenario Evidence Matrix

Each row maps a PRD Goal to its UAT ID, preconditions, expected threshold, and required recorded evidence. Protocol approval for Goal 1 must be on record before the reliability exercise is marked passed.

| Goal | UAT ID | Preconditions | Test data / fixture | Steps | Oracle | Expected threshold | Recorded evidence |
|---|---|---|---|---|---|---|---|
| Goal 1 | UAT-BA-009 | Approved sampling protocol; controlled service; valid authenticated session; 3 workflow types allocated | 100 recorded runs across direct-text, prompt-file, prompt+doc | Run 100 trials; count successes | Success count / total | ≥ 99/100 | Commit SHA, environment, tier/region, timestamps, run IDs, exclusion reasons, QA approval signature, release disposition |
| Goal 2 | UAT-BA-010 | Runs complete terminal success | Reconciliation fixture comparing run records to output files | Compare 100% of successful runs | Reconciliation report | 100% have both artifacts | Measured value, reviewer approval, commit |
| Goal 3 | UAT-BA-011 | CLI and MCP surfaces available | 3-workflow parity fixture | Run all 3 workflows on both surfaces | Response envelope | 3/3 workflows parity | Per-surface output diff, commit |
| Goal 4 | UAT-BA-012 | 30 queued-run trials | Async acknowledgement timer | Measure elapsed from submission to ID receipt; sort 30 values | p95 = sorted value at index 28 (0-indexed), i.e. the 29th smallest of 30, matching `int(0.95 * 30) = 28` in `tests/uat_fixtures.py:measure_async_p95` | p95 ≤ 2.0 s | 30 trial timestamps, p95 calculation documented, commit |
| Goal 5 | UAT-BA-013 | 10 concurrent runs | 10-run isolation fixture with 1 forced auth failure | Run all 10; force failure in run 2 | Unaffected run completion | 9/9 unaffected reach terminal | Run IDs, failure reason, commit, reviewer sign-off |

Each exercise records: commit, environment, tier/region, timestamps, run IDs, redacted result evidence, measured values, reviewer approval, and release disposition. Do not mark live exercises as passed based on unit tests alone; use controlled fixtures where appropriate and authorized live sessions for upstream-dependent claims. Protocol approval stays a dependency of the reliability exercise (Goal 1).


## Isolated UAT setup

