# Reproducible Demo

1. Create a temporary workspace and prompt: `mkdir -p /tmp/qwen-demo && printf "# Summarize\nSummarize the input." > /tmp/qwen-demo/prompt.md`.
2. Initialize it: `QWEN_WORKSPACE_ROOT=/tmp/qwen-demo qwen-web-arwaky init`.
3. Run the headless flow: `qwen-web-arwaky prompt-only -i /tmp/qwen-demo/prompt.md -o /tmp/qwen-demo/output.md --headless`.
4. Inspect `/tmp/qwen-demo/output.md` and the JSONL logs under the configured XDG jobs directory.
5. For MCP, call `process_prompt_file_only` with the in-workspace prompt, then poll `get_job_status` until `completed` is true.

The demo intentionally uses a temporary workspace and does not delete user data.
