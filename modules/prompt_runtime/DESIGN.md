# DESIGN — Prompt Runtime

## Design Overview

A browser/stream capability contract for the prompt feature (`modules/prompt_runtime`): five runtime capabilities drive the live Playwright page and the output filesystem, one aggregate fronts them as a single verb door, and the design carries no verb routing or cancellation logic of its own — those live in `modules/prompt`.

## Design Requirements

### DS-PROMPT-RUNTIME-001: Capability Boundaries

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Stream monitor | Watches the page until a response completes; stall/timeout verdicts | `StreamMonitor` | watch |
| Send dispatcher | Clicks send; parse-toast hold loop | `SendDispatcher` | send |
| Prompt injector | DOM-injects prompt text into the chat input | `PromptInjector` | inject |
| File uploader | Attachment validation and upload | `FileUploader` | upload |
| Output saver | Markdown persistence + `.meta.json` sidecar | `Saver` | persist |

### DS-PROMPT-RUNTIME-002: Barrel and Packaging

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Import point | `src/__init__.py` re-exports the five capability classes | `__all__` | single import point |
| Packaging | Per-member `pyproject.toml` is additive setuptools metadata under the root | `packages.find` | additive, not standalone-buildable |

### DS-PROMPT-RUNTIME-003: Dependency Isolation

| Variant | Use case | Token | Value |
| --- | --- | --- | --- |
| Allowed imports | Depends only on `modules.shared` (taxonomy, contract, utility) plus `playwright` | `modules.shared` | no cross-module capability imports |
| Artifact perms | `Saver.write_output` enforces `0o600` on written artifacts | `0o600` | owner read/write only |
| Upload ceiling | `FileUploader.validate_file` enforces the `100 * 1024 * 1024` byte ceiling pre-flight | `104857600` | shared taxonomy constant |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals, user stories, and scope | [PRD.md](../../PRD.md) |
| Backlog | Task tracking, epics, and implementation status | [BACKLOG.md](BACKLOG.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
