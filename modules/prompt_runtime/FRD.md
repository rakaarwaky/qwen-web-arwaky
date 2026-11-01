# PROMPT-RUNTIME Functional Requirements Document

## Feature Overview

The prompt-runtime feature is the browser/stream/persist capability layer
behind one prompt run. It owns five capabilities that drive the live
Playwright page and the output filesystem — prompt injection, send
dispatch, response watch, attachment upload, and artifact persistence —
and one aggregate, `IPromptRuntimeAggregate`, whose `execute` door routes
a request verb to the capability that serves it.

## Functional Requirements

### FR-PromptRuntime-001: Inject prompt text into the chat input

**Description:**

Locate the chat input on the live page and inject the prompt text through multi-strategy DOM injection, verifying the text landed.

#### Business Logic

- Empty or whitespace-only prompt text is rejected before any DOM work (`PromptInjectionError`).
- The input element must exist; a missing input is a hard error naming the selector it waited on (`ElementNotFoundError`).
- Verification confirms the element's value matches the injected text before `inject_text` returns, so a silent fill failure surfaces.

#### Edge Cases

- React-controlled value setters defeat a plain `fill()`, so the capability falls back to a React setter and then to `type()`.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request with verb `inject`, the live page, the prompt text, and the optional injector configuration. |
| **Output** | The default runtime response (the injection itself is void-handed; the input element's value is the observable effect). |
| **Protocol** | `IRuntimeInjectProtocol` — one of the six protocol seam classes declared by the prompt feature in the shared contract kernel. |
| **Method** | `find_input` locates the input element; `inject_text` performs the multi-strategy injection. |
| **Event** | `prompt_injected` — emitted after the injection verifies the value landed. |
| **Error** | A missing input element raises `ElementNotFoundError`; an injection that exhausts every strategy (React setter, then `type()`) raises an injection error naming the prompt. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| Prompt text is injected via the shared `IInjectionProtocol` seam | The live page is driven through the pipeline | The injection verifies the value landed |

#### Metric

| Target Metric | Value |
| --- | --- |
| Injection verification pass rate | 100% |

### FR-PromptRuntime-002: Dispatch the send action

**Description:**

Click the send control on the live page and confirm the dispatch was acknowledged, then report the post-dispatch turn count.

#### Business Logic

- Dispatch is refused while `document_parsed` is False — clicking send during attachment parsing triggers Qwen's parse toast or bot verification (`SendDispatchError`).
- An acknowledgment is a real new user turn (message count growth, user-bubble growth, or changed latest text); a cleared composer or disabled button is not evidence.
- A parse toast appearing after the click holds the dispatch loop until parsing finishes rather than re-sending into it.
- Enter is the keyboard fallback when the send button never clicks.
- Missing lifecycle emitter is refused before any DOM work (`QwenCliError`).

#### Edge Cases

- A page that resets the composer without committing the turn does not acknowledge; the wait times out and reports a dispatch failure instead of falsely succeeding.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request with verb `send`, the live page, the lifecycle emitter, the optional sender configuration, and the `document_parsed` gate. |
| **Output** | The runtime response carrying the chat turn count observed after dispatch (`message_count`). |
| **Protocol** | `IRuntimeSendProtocol` — one of the six protocol seam classes declared by the prompt feature in the shared contract kernel. |
| **Method** | `click_send` dispatches; `count_messages` and `latest_message_text` report the post-dispatch state. |
| **Event** | `send_clicked` — emitted after an acknowledgment is observed. |
| **Error** | A control that never clicks, or a click that never acknowledges, surfaces `SendDispatchError` carrying the reason. A missing lifecycle emitter is refused before any DOM work (`QwenCliError`). |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| Send dispatch routes through the shared `ISendProtocol` seam | The live page is driven through the pipeline | The ACK gate confirms a real new user turn |

#### Metric

| Target Metric | Value |
| --- | --- |
| ACK gate pass rate | 100% |

### FR-PromptRuntime-003: Watch the response stream

**Description:**

Follow the response stream until a stable terminal state is reached, the stall detector fires, or the ceiling elapses.

#### Business Logic

- The extraction verdict is `complete` on a terminal, validated, stable response (`StreamVerdict`); the `stalled` and `incomplete` outcomes are produced by this feature and reported by the prompt feature.
- `timeout_sec` is a hard wall-clock cutoff, not an idle budget: a long thinking phase consumes it (`ResponseDetectionTimeoutError`).
- The stall detector is event-driven (no forward event — thinking, text change, completion — inside the stall window) and raises `StuckDetectedError`, terminal for the run.
- A set cancel token raises `RunCancelledError` before and during the wait so only the owning run stops.
- Response content is validated before `complete` is claimed (empty/challenge/error pages never pass as answers).
- Missing lifecycle emitter is refused before any DOM work (`QwenCliError`).

#### Edge Cases

- A stream that emits no forward event for the full stall window reports `stalled`; a hard ceiling crossing reports `incomplete`.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request with verb `watch`, the live page, the response timeout, the message count before dispatch, the lifecycle emitter, and the optional streamer configuration plus an optional cancel token. |
| **Output** | The runtime response carrying the stable response text and the extraction verdict (`response_text`, `verdict`). |
| **Protocol** | `IRuntimeWatchProtocol` — one of the six protocol seam classes declared by the prompt feature in the shared contract kernel. |
| **Method** | `wait_for_response` drives the stream to a verdict; `is_generation_complete` and `is_thinking_active` probe the terminal state. |
| **Event** | `generation_finished` — emitted when the stable terminal state is reached. |
| **Error** | A hard ceiling crossing raises `ResponseDetectionTimeoutError`; the stall detector raises `StuckDetectedError`; a cancel token raises `RunCancelledError`; a missing lifecycle emitter is refused before any DOM work (`QwenCliError`). |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| Watch routes through the shared `IStreamProtocol` seam | The live page is driven through the pipeline | The verdict is `complete` on a stable terminal state |

#### Metric

| Target Metric | Value |
| --- | --- |
| Stream verdict accuracy | 100% |

### FR-PromptRuntime-004: Upload an attachment

**Description:**

Validate an attachment file against the locked allowlist and byte ceiling, then attach it to the page and wait for both backend parse and DOM parse readiness.

#### Business Logic

- Pre-flight runs before any browser work: extension allowlist, zero-byte rejection, and the exact byte ceiling of `104857600` bytes — a strictly-over file is rejected with the limit named, a file exactly at the ceiling passes.
- Upload is refused while `web_loaded` is False (`RuntimeError`) — the page must be ready before the chooser opens.
- Attachment-card presence is verified by filename match across the configured selector families in one `page.evaluate` probe per poll.
- Document parse is dual-gated: the backend `/files/parse` completion and a DOM readiness pass (no toast, no pending spinner) both must clear before the capability reports accepted.

#### Edge Cases

- A file that validates but never renders a card surfaces a timeout naming the file.
- Transient Playwright errors during the card poll are retried within the deadline, while a card-shaped parse answer of the wrong type is a contract violation.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request with verb `upload`, the live page, the file path, the optional lifecycle emitter, and the `web_loaded` gate. |
| **Output** | The runtime response carrying the acceptance verdict (`accepted`). |
| **Protocol** | `IRuntimeUploadProtocol` — one of the six protocol seam classes declared by the prompt feature in the shared contract kernel. |
| **Method** | `validate_file` runs pre-flight; `upload_attachment` attaches and waits for dual parse readiness. |
| **Event** | `file_uploaded` — emitted when the attachment card and parse gates clear. |
| **Error** | A pre-flight failure returns not-accepted (`accepted=False`); a card or parse timeout returns not-accepted with the reason logged; a web-not-loaded gate raises. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An attachment over 104857600 bytes | Pre-flight runs | The file is rejected before the browser |
| An attachment exactly at the 104857600-byte ceiling | Pre-flight runs | The file is accepted |

#### Metric

| Target Metric | Value |
| --- | --- |
| Pre-flight boundary accuracy | 100% |

### FR-PromptRuntime-005: Persist the response artifact

**Description:**

Write the response text to the operator's named destination with a run-traceability `.meta.json` sidecar.

#### Business Logic

- The artifact is written `0o600` (owner read/write only) on both the atomic and direct paths.
- The `.meta.json` sidecar lands under the XDG metadata directory (`DEFAULT_METADATA_DIR` by default), never beside the output.
- A directory destination gets a generated collision-free name; an explicitly named file is honored exactly as written and overwritten in place.
- The sidecar is mandatory traceability: its failure raises after the main artifact is safely on disk so the artifact stays inspectable.
- A missing `output_path` is refused before any write (`QwenCliError`).

#### Edge Cases

- A run without its own context defaults to a fresh run context.
- UI noise (thinker/app chrome markers) is stripped from the content before the write.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request with verb `persist`, the output path, the response content, the run context, the source file, duration and character counts, plus the optional saver configuration. |
| **Output** | The runtime response carrying the saved path and the written text (`saved_path`, `response_text`). |
| **Protocol** | `IRuntimePersistProtocol` — one of the six protocol seam classes declared by the prompt feature in the shared contract kernel. |
| **Method** | `write_output` writes the artifact and its `.meta.json` sidecar. |
| **Event** | `output_copied` — emitted when both the artifact and the sidecar are on disk. |
| **Error** | A write failure surfaces `OutputWriteError` naming the path; a missing `output_path` is refused before any write (`QwenCliError`). |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A persisted artifact on disk | A mode check runs after a real write | The artifact is `0o600` |
| The `.meta.json` sidecar | A path assertion runs after a real write | The sidecar lands in the metadata dir, never beside the artifact |

#### Metric

| Target Metric | Value |
| --- | --- |
| Artifact permission correctness | 100% |

### FR-PromptRuntime-006: Route any runtime verb through one aggregate door

**Description:**

`IPromptRuntimeAggregate.execute` is the single door over the five capabilities: one request verb selects exactly one capability method, so no surface branches on verbs itself.

#### Business Logic

- A verb is added as a `RuntimeRequest` variant, never as a second aggregate method.
- A verb outside the five (or one added to `RuntimeVerb` without a wired capability) raises `QwenCliError` naming the verb.
- A verb called with a missing required slot (`emitter` for `send`/`watch`, `filepath` for `upload`, `output_path` for `persist`) raises `QwenCliError` naming the slot instead of failing deep in the capability.
- The agent imports only shared contracts, taxonomy, and utility — never a runtime capability module, never a surface.

#### Edge Cases

- Two consumers holding the same aggregate see one routing behaviour; per-verb differences live in the request fields, not in the door's shape.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A runtime request naming one of `inject`, `send`, `watch`, `upload`, `persist` plus that verb's fields. |
| **Output** | The runtime response shaped by the routed verb: turn count (`send`), text + verdict (`watch`), acceptance (`upload`), saved path + text (`persist`), default (`inject`). |
| **Protocol** | `IRuntimeDoorProtocol` — the aggregate door contract that fronts the five capability seams. |
| **Method** | `execute` routes one request verb to exactly one capability method. |
| **Event** | Varies by the routed verb — each capability emits its own event. |
| **Error** | An unknown verb or a missing required slot raises `QwenCliError` before any capability runs. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A verb outside the runtime set | The door routes | `QwenCliError` names the verb |
| A `send`/`watch` without an emitter | The door routes | `QwenCliError` names the missing slot |

#### Metric

| Target Metric | Value |
| --- | --- |
| Boot-to-persist latency | well under 5 seconds |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `PromptRuntimeOrchestrator` |
| Aggregate | `IPromptRuntimeAggregate` |
| Method | `execute` |
| Request | `RuntimeRequest` — variants `inject`, `send`, `watch`, `upload`, `persist` |
| Response | `RuntimeResponse` — shaped by the routed verb: turn count (`send`), text + verdict (`watch`), acceptance (`upload`), saved path + text (`persist`), default (`inject`) |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
