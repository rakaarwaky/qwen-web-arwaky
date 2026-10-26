# DESIGN — Prompt Orchestration

> Pipeline/orchestration layer contract for the prompt feature
> (`modules/prompt`).
> Audience: agent engineers, orchestrator integrators.
> Condition: [ROADMAP.md](../../ROADMAP.md) (workspace) + [FRD.md](FRD.md) (this layer).

## Brand & Style

Orchestration layer (AES405). Decides *which* verb runs and *how* in-flight
runs are cancelled; it never touches the browser or DOM. The browser/stream
capabilities live in `modules/prompt_runtime`, reached only through the
protocols in `modules/shared/src/prompt/contract_prompt_protocol.py`.

## Components

| Component | Class | Layer | Role |
|---|---|---|---|
| `agent_prompt_orchestrator` | `PromptOrchestrator` | Agent | Verb routing (`direct`, `file`, `attachment`, `cancel`); builds the per-verb adapters. |
| `capabilities_direct_prompt_adapter` | `DirectPromptAdapter` | Agent | Inline text prompt flow. |
| `capabilities_prompt_file_adapter` | `PromptFileAdapter` | Agent | Prompt-file-only flow. |
| `capabilities_attachment_prompt_adapter` | `AttachmentPromptAdapter` | Agent | Prompt-file + attachment flow; resolves folder attachments through the jobs contract. |
| `capabilities_prompt_flow_dispatcher` | `PromptFlowDispatcher` | Capabilities | Shared inject → send → wait flow with the retry budget. |
| `capabilities_run_cancel_registry` | `RunCancelRegistry` | Capabilities | Targeted cancel: signals a specific in-flight run without affecting others. |

The adapters take protocol-typed constructor arguments (`IInjectionProtocol`,
`ISendProtocol`, `IStreamProtocol`, `ISaverProtocol`, `IUploadProtocol`,
`IRunCancelProtocol`); the root container wires the concrete implementations.

### Dependency Notes

- Depends on `modules.shared` (taxonomy, contract, utility) — no other module's
  concrete capabilities.
- `PromptFlowDispatcher` receives `injector` / `sender` / `streamer` / `saver`
  as constructor parameters typed to protocols, never as concrete imports
  (AES403: capabilities never import other capabilities).
- Cancellation is targeted: `RunCancelRegistry` keys the signal to a run id,
  so an unrelated in-flight run is not interrupted.

## Reference

- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- Runtime layer: [modules/prompt_runtime/DESIGN.md](../prompt_runtime/DESIGN.md)
