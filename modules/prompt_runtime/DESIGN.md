# DESIGN — Prompt Runtime

> Browser/stream capability contract for the prompt feature
> (`modules/prompt_runtime`).
> Audience: capability engineers, agent integrators.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [FRD.md](../prompt/FRD.md) (prompt).

## Brand & Style

Smart capability layer (AES403). The five runtime capabilities drive the live
Playwright page and the output filesystem; they carry no verb-routing or
cancellation logic (that lives in `modules/prompt`). They emit pipeline
lifecycle events but log only lengths and counts, never response text.

## Components

| Capability | Class | Role |
|---|---|---|
| `capabilities_stream_monitor` | `StreamMonitor` | Watches the page until a response completes; stall/timeout verdicts. |
| `capabilities_send_dispatcher` | `SendDispatcher` | Clicks send; parse-toast hold loop. |
| `capabilities_prompt_injector` | `PromptInjector` | DOM-injects prompt text into the chat input. |
| `capabilities_file_uploader` | `FileUploader` | Attachment validation and upload. |
| `capabilities_output_saver` | `Saver` | Markdown persistence + `.meta.json` sidecar. |

### Barrel

`src/__init__.py` is the module's single import point; it re-exports the five
capability classes (`FileUploader`, `PromptInjector`, `SendDispatcher`,
`Saver`, `StreamMonitor`) under `__all__`.

### Packaging

The per-member `pyproject.toml` is additive setuptools metadata under the
root `packages.find include = ["modules*"]`; it is not a uv workspace
member and is not standalone-buildable (matches the pre-existing
`modules/shared` / `modules/cli` convention).

### Dependency Notes

- Depends only on `modules.shared` (taxonomy, contract, utility) plus
  `playwright` — no cross-module capability imports.
- `Saver.write_output` enforces `0o600` on written artifacts; the `.meta.json`
  sidecar lands under XDG state, never the output directory.
- `FileUploader.validate_file` enforces the `100 * 1024 * 1024` byte ceiling
  pre-flight; the limit is a shared taxonomy constant.

## Reference

- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- Orchestration layer: [modules/prompt/DESIGN.md](../prompt/DESIGN.md)
