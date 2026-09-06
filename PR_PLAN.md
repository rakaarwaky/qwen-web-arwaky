# PR: feat(prompt-template): Built-in Role Prompt Templates (CLI/MCP/TUI)

> **Repo:** `internal/qwen-web-arwaky`
> **Branch:** `feat/prompt-templates` (from `main`)
> **Target:** Upstream PR → `main`
> **AES compliance:** 7-layer, naming `{layer}_{concern}_{role}.py`
> **Mypy strict · Ruff · Bandit · 100% tests for new code**

---

## 🎯 Executive Summary

Tambahkan dukungan **built-in role prompt templates** (`architect`, `backend`, `frontend`, `analyst`) ke argumen prompt path (`-i` / `--prompt-path` di CLI, `input_file` / `prompt_file` di MCP, dan input prompt file di TUI).

Pengguna dan AI agent cukup memasukkan nama role, sistem secara transparan meresolusi dan mematerialisasi template review markdown bawaan ke file temporer (`/tmp/qwa-templates/{role}.md`) dan meneruskannya ke pipeline existing tanpa memerlukan orchestrator atau perombakan pipeline baru.

**4 role bawaan:**

| Role | Slug | Dimensions |
|------|------|-----------|
| Architect | `architect` | Layer Boundaries · Naming · Orphan · Scalability · Data Flow |
| Backend / Tech Lead | `backend` | Security · Performance · Error Handling · SOLID · Code Quality · Maintainability |
| Frontend / UI-UX | `frontend` | Accessibility · Responsiveness · UX Patterns · Component Quality · Visual Consistency · Client Performance |
| Business Analyst | `analyst` | Requirements Clarity · Business Flow · Logic Implementation · Testability · Traceability |

**Prinsip Ponytail/Lean:** zero-network, pure-string templates, idempotent, AES-compliant, tanpa subcommand baru, tanpa kontrak/agent baru, tanpa dependensi eksternal baru.

---

## 🧩 Arsitektur AES

### Layer mapping (sesuai AGENTS.md)

```
modules/shared/src/
  ├── taxonomy_architect_constant.py   (NEW)  EMBEDDED_ARCHITECT_TEMPLATE
  ├── taxonomy_backend_constant.py     (NEW)  EMBEDDED_BACKEND_TEMPLATE
  ├── taxonomy_frontend_constant.py    (NEW)  EMBEDDED_FRONTEND_TEMPLATE
  ├── taxonomy_analyst_constant.py     (NEW)  EMBEDDED_ANALYST_TEMPLATE
  ├── taxonomy_core_constant.py        (EXTEND) PROMPT_TEMPLATE_MANIFEST, PROMPT_TEMPLATE_ROLES
  └── utility_core_prompt_template.py  (NEW)  is_prompt_role, load_prompt_template, materialize_role_template

modules/
  ├── root_cli_main_entry.py           (EXTEND) role detection in _build_config()
  └── root_mcp_main_entry.py           (EXTEND) documentation for role inputs

modules/mcp/src/
  └── surface_mcp_tool_command.py      (EXTEND) role resolution in process_prompt_file_only & process_prompt_with_attachment

modules/cli/src/
  └── surface_cli_tui_app.py           (EXTEND) role resolution in action_run_action()

tests/
  ├── unit_utility_prompt_template.py  (NEW)  unit tests for template loading and materialization
  └── integration_prompt_template.py   (NEW)  integration tests across CLI, MCP, and TUI
```

---

## 🚀 Use Cases & UX

### 1. CLI — Review Attachment dengan Role Template
```bash
# Code review dengan backend template
qwen-web-cli prompt-with-attachment -i backend -a src/auth.py --headless --json

# Architecture review
qwen-web-cli prompt-with-attachment -i architect -a README.md --headless --json
```

### 2. MCP — Review Attachment dengan Role Template
```json
{
  "tool": "process_prompt_with_attachment",
  "params": {
    "prompt_file": "architect",
    "attachment_file": "/path/to/code.py"
  }
}
```

### 3. TUI — Input Prompt Field
Pengguna dapat mengetikkan `architect`, `backend`, `frontend`, atau `analyst` di field *Prompt File*, dan sistem akan mematerialisasikannya otomatis saat eksekusi dijalankan.

---

## 🧪 Verifikasi & Status

- [x] Template taxonomy constants (4 file)
- [x] Utility resolver & materializer (`utility_core_prompt_template.py`)
- [x] CLI entry point resolution (`root_cli_main_entry.py`)
- [x] MCP surface resolution (`surface_mcp_tool_command.py`)
- [x] MCP entry documentation (`root_mcp_main_entry.py`)
- [x] TUI surface resolution (`surface_cli_tui_app.py`)
- [x] Unit tests (`tests/unit_utility_prompt_template.py`)
- [x] Integration tests (`tests/integration_prompt_template.py`)
- [x] SKILL.md guide updated
- [x] Ruff clean (0 errors)
- [x] Mypy strict clean (0 errors)