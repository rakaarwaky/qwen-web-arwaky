---
name: qwen-web
description: >
  Automate Qwen AI Web (chat.qwen.ai) with the Qwen3.8-Max intelligence model —
  zero API keys, persistent browser sessions. Use when an AI agent needs to send
  prompts, review code, or analyze document attachments via CLI or MCP tools.
version: 6.0.0
triggers:
  - qwen
  - chat.qwen.ai
  - prompt automation
  - code audit
  - architecture review
  - deep reasoning
  - document analysis
  - no api key
entry_points: [qwen-web-arwaky, qwa, qwen-web-mcp]
---

# Qwen Web Automation Skill Guide

Use this skill when an AI agent needs to send prompts or document files to **Qwen AI (`chat.qwen.ai`)** and receive complete responses via MCP tools or CLI commands.

---

## 1. Quick Reference: MCP Tools & CLI Commands

| Action | MCP Tool | CLI Command (`qwa` / `qwen-web-arwaky`) |
| :--- | :--- | :--- |
| Direct text prompt | `process_direct_prompt` | `qwa prompt-direct -t "<prompt>" [-o <out>]` |
| Prompt file only | `process_prompt_file_only` | `qwa prompt-only -i <prompt.md> [-o <out>]` |
| Prompt with attachment | `process_prompt_with_attachment` | `qwa prompt-with-attachment -i <prompt.md> -a <file> [-o <out>]` |
| Check session health | `check_session` | `qwa doctor` |
| Manual login / CAPTCHA | `setup_session` | `qwa login` |
| Reset session | `delete_session` | — |
| Initialize workspace | `init_workspace` | `qwa init` |

> **File conventions:** Place inputs under `.qwen-web/input/` and outputs under `.qwen-web/output/`. Always append a timestamp to output filenames (e.g., `arch_review_$(date +%Y%m%d_%H%M%S).md` in CLI or `YYYYMMDD_HHMMSS` in MCP) to prevent overwriting results from previous runs.

---

## 2. Usage by Use Case

### Use Case 1: Quick Inline Prompt / Question
Use for fast queries, factual explanations, or one-off code generation where no external files are needed.

**MCP:**
```json
{
  "prompt": "Explain the difference between optimistic and pessimistic locking in 3 concise bullet points with a brief Python example.",
  "headless": true
}
```

**CLI:**
```bash
qwa prompt-direct -t "Explain optimistic vs pessimistic locking" -o .qwen-web/output/locking_$(date +%Y%m%d_%H%M%S).md --headless
```

---

### Use Case 2: Complex Task from a Prompt File
Use for multi-step instructions, complex refactor specs, or long prompts authored in a Markdown file.

**MCP:**
```json
{
  "input_file": ".qwen-web/input/refactor_task.md",
  "output_file": ".qwen-web/output/refactor_result_20260911_133000.md",
  "headless": true
}
```

**CLI:**
```bash
qwa prompt-only -i .qwen-web/input/refactor_task.md -o .qwen-web/output/refactor_result_$(date +%Y%m%d_%H%M%S).md --headless
```

---

### Use Case 3: Code Audit or Document Analysis with Attachment
Use when the prompt requires analyzing a codebase export, technical document, log file, or PDF spec (supported: `.pdf`, `.md`, `.txt` up to 100 MB).

**MCP:**
```json
{
  "prompt_file": ".qwen-web/input/audit_spec.md",
  "attachment_file": ".qwen-web/input/codebase_export.md",
  "output_file": ".qwen-web/output/audit_findings_20260911_133000.md",
  "headless": true
}
```

**CLI:**
```bash
qwa prompt-with-attachment -i .qwen-web/input/audit_spec.md -a .qwen-web/input/codebase_export.md -o .qwen-web/output/audit_findings_$(date +%Y%m%d_%H%M%S).md --headless
```

---

### Use Case 4: Standard Reviews Using Built-in Role Templates
Instead of writing a custom prompt file, you can pass a built-in role template name directly as the prompt input:
- `backend`: Security, performance, error handling, code quality, and maintainability.
- `architect`: Layer boundaries, architecture violations, scalability, and data flow.
- `frontend`: Usability, responsive layout, component quality, and design tokens.
- `analyst`: Requirements clarity, business logic flow, and testability.

**MCP:**
```json
{
  "prompt_file": "backend",
  "attachment_file": "src/api/auth.py",
  "output_file": ".qwen-web/output/auth_review_20260911_133000.md"
}
```

**CLI:**
```bash
qwa prompt-with-attachment -i backend -a src/api/auth.py -o .qwen-web/output/auth_review_$(date +%Y%m%d_%H%M%S).md --headless
qwa prompt-with-attachment -i architect -a README.md -o .qwen-web/output/arch_review_$(date +%Y%m%d_%H%M%S).md --headless
```

---

### Use Case 5: Session Setup & Authentication
Use to verify login status or authenticate a new browser session when cookies expire.

1. **Check session health:**
   - MCP: call `check_session`
   - CLI: `qwa doctor`
2. **Login / Re-authenticate (opens visible browser for login / CAPTCHA):**
   - MCP: call `setup_session`
   - CLI: `qwa login`
3. **Reset session profile (if corrupted):**
   - MCP: `delete_session` with `{"confirm": true}`

---

### Use Case 6: Workspace Initialization
Use when provisioning `.qwen-web/` workspace directories and sample configuration in a new project.

**MCP:**
```json
{
  "target_dir": "."
}
```

**CLI:**
```bash
qwa init
```

---

## 3. Prompt Engineering for Complete, Un-Truncated Output

To ensure Qwen produces complete code without placeholders or omitted sections:

1. **Specify an explicit Output Contract:** Define exact required section titles and expected markdown formatting.
2. **Forbid truncation explicitly:** Include this clause in your prompt:
   > *"Output every file COMPLETE and VERBATIM inside fenced code blocks with language tags. Never use ellipses (`...`), placeholder comments (`// rest unchanged`), or omit code."*
3. **Reason first, code second:** Request an analysis or plan before the implementation code so the model thinks before writing.
4. **Put large context into attachments:** Keep the prompt file focused on instructions; provide code, logs, and schemas as attachments.
5. **Add a self-verification step:** Instruct the model to verify that no placeholders exist and all requested items are satisfied before completing.

---

## 4. Error Handling & Recovery

| Error / Condition | Cause | Action |
| :--- | :--- | :--- |
| `AuthRequiredError` / `AUTH_REQUIRED` | Session expired or login needed | Call `setup_session` (MCP) or run `qwa login` (CLI) to re-authenticate. |
| `OutputValidationError` (CAPTCHA) | Bot verification challenge | Run `setup_session` or `qwa login` to solve challenge manually. |
| `NetworkTimeoutError` | Temporary network latency | Retry the request; if persistent, verify internet connection via `qwa doctor`. |
| `FileValidationError` / `FILE_NOT_FOUND` | Missing, unreadable, or file > 100 MB | Verify file path, permissions, and ensure file size is under 100 MB. |
| `CircuitBreakerOpenError` | Repeated consecutive failures | Wait 30 seconds before sending next request. |
| `VALIDATION_ERROR` (MCP) | Invalid tool parameter | Check error `field` in response and correct the argument payload. |
