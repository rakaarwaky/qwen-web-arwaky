---
name: qwen-web
description: Automate Qwen AI Web (chat.qwen.ai) prompt processing via CLI or MCP tools without requiring official API keys.
---
# Qwen Web Automation & MCP Server Skill Guide

Use this skill when an AI agent needs to send prompts or document files to **Qwen AI (`chat.qwen.ai`)** and receive generated AI responses via MCP tools or CLI execution.

---

## Available MCP Tools

| MCP Tool Name               | Description                                      | Key Parameters                                                                                  |
| :-------------------------- | :----------------------------------------------- | :---------------------------------------------------------------------------------------------- |
| `process_direct_prompt`     | Process a direct text prompt string              | `prompt` (str), `timeout_sec` (int, default 120), `headless` (bool, default true)               |
| `process_prompt_file_only`  | Process a single Markdown prompt file            | `input_file` (str), `output_file` (optional str), `headless` (bool)                             |
| `process_prompt_with_attachment` | Process a prompt file with a document attachment | `prompt_file` (str), `attachment_file` (str), `output_file` (optional str), `headless` (bool) |
| `setup_session`             | Launch visible browser for manual login          | None                                                                                            |

---

## Usage Guidelines for AI Agents

### Direct Text Queries (`process_direct_prompt`)

Use for one-shot prompts where text is provided directly. Supports long deep-thinking prompts up to 900s (15 min) with proactive 30s cloud reload sync for network resilience.

```json
{
  "prompt": "Analyze the following system architecture and summarize key bottlenecks...",
  "timeout_sec": 120,
  "headless": true
}
```

### File Processing (`process_prompt_file_only`)

Use when processing an existing Markdown prompt file stored on disk.

```json
{
  "input_file": "input/role-architect/task_001.md",
  "output_file": "output/role-architect/task_001.md"
}
```

### File Processing With Attachment (`process_prompt_with_attachment`)

Use when the prompt file must be sent together with a document attachment.

```json
{
  "prompt_file": "input/role-architect/task_001.md",
  "attachment_file": "input/role-architect/docs/spec.pdf",
  "output_file": "output/role-architect/task_001.md"
}
```

### Parallel Job Execution

Multiple prompt jobs can run concurrently against one authenticated browser session. Each worker job launches its own dedicated Chromium browser instance using an isolated ephemeral clone of the master login session profile, enabling N jobs to run in parallel without tab collisions or SingletonLock conflicts.

- **Concurrency limit**: controlled by `QWEN_WEB_MAX_WORKERS` (default 2). Set higher to increase throughput; all workers share the same authenticated login session.
- **Isolated processes**: 1 browser process per job with clean ephemeral state; temporary profile clones are automatically purged on completion.
- **Login mode**: `setup_session` operates directly on the master session profile so authenticated credentials persist across runs.

```bash
# Run 4 prompt files concurrently (2 at a time by default):
QWEN_WEB_MAX_WORKERS=4 qwa process input/task_001.md input/task_002.md input/task_003.md input/task_004.md
```

### Built-in Role Prompt Templates

Instead of creating a Markdown prompt file manually, you can pass a built-in role template name wherever a prompt file path is accepted (`input_file`, `prompt_file`, or CLI `-i` / `--prompt-path`):
- `architect`: Layer Boundaries, Naming, Orphan, Scalability, Data Flow
- `backend`: Security, Performance, Error Handling, SOLID, Code Quality, Maintainability
- `frontend`: Accessibility, Responsiveness, UX Patterns, Component Quality, Visual Consistency, Client Performance
- `analyst`: Requirements Clarity, Business Flow, Logic Implementation, Testability, Traceability

#### MCP Example (Attachment Review with Role Template)
```json
{
  "prompt_file": "backend",
  "attachment_file": "src/api/auth.py"
}
```

#### CLI Example
```bash
# Code review with backend template and attachment
qwen-web-cli prompt-with-attachment -i backend -a src/auth.py --headless --json

# Architecture review
qwen-web-cli prompt-with-attachment -i architect -a README.md --headless --json
```

### Session Authentication (`setup_session`)

If session cookies expire or CAPTCHA is detected, invoke `setup_session` to launch a visible browser window for manual user login.

---

## Error Handling for Agents

| Exception | Meaning | Agent Action |
| :--- | :--- | :--- |
| `AuthRequiredError` | Session expired or CAPTCHA detected | Call `setup_session` for re-authentication |
| `NetworkTimeoutError` | Browser network timeout | Retry with increased `timeout_sec` |
| `OutputValidationError` | Response contains error page or CAPTCHA | Retry or check input quality |
| `CircuitBreakerOpenError` | Too many consecutive failures | Wait and retry later |
| `PromptInjectionError` | Text injection failed | Check if Qwen UI has changed |

---

## Session Management

- Session cookies stored in `qwen_session/` (persistent across runs).
- First run requires `--login` or interactive mode for manual authentication.
- Subsequent runs can use `--headless` mode.
- Session health checked automatically before each file processing.
