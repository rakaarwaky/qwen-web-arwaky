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
