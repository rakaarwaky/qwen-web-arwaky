# PROMPT-RUNTIME Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)
- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)

## System Overview

The prompt-runtime feature is the browser/stream/persist capability layer
behind one prompt run. It owns five capabilities that drive the live
Playwright page and the output filesystem — prompt injection, send
dispatch, response watch, attachment upload, and artifact persistence —
and one aggregate, `IPromptRuntimeAggregate`, whose `execute` door routes
a request verb to the capability that serves it.

The feature does no verb routing of its own pipeline: the ordering
(inject → send → wait → save) belongs to the prompt feature's shared flow
dispatcher behind the prompt aggregate, and the runtime aggregate never
re-sequences it. Each capability fulfils a protocol seam the prompt
feature declared in the shared contract kernel, so consumers depend on
shared contracts, never on this feature's capabilities.

## Functional Requirements

### FR-RUNTIME-001: Inject prompt text into the chat input

- **Description**: Locate the chat input on the live page and inject the
prompt text through multi-strategy DOM injection, verifying the text
landed.
- **Input**: A runtime request with verb `inject`, the live page, the
prompt text, and the optional injector configuration.
- **Output**: The default runtime response (the injection itself is
void-handed; the input element's value is the observable effect).
- **Business Rules**:
  - Empty or whitespace-only prompt text is rejected before any DOM work
  (`PromptInjectionError`).
  - The input element must exist; a missing input is a hard
  (`ElementNotFoundError`) naming the selector it waited on.
  - Verification confirms the element's value matches the injected text
  before `inject_text` returns, so a silent fill failure surfaces.
- **Edge Cases**: Whoever answers; React-controlled value setters defeat
a plain `fill()`, so the capability falls back to a React setter and
then to `type()`.
- **Error Handling**: A not-found input surfaces an element-not-found
error naming the selector; an injection that exhausts every strategy
surfaces an injection error naming the prompt (never a silent miss).

### FR-RUNTIME-002: Dispatch the send action

- **Description**: Click the send control on the live page and confirm
the dispatch was acknowledged, then report the post-dispatch turn count.
- **Input**: A runtime request with verb `send`, the live page, the
lifecycle emitter, the optional sender configuration, and the
`document_parsed` gate.
- **Output**: The runtime response carrying the chat turn count observed
after dispatch (`message_count`).
- **Business Rules**:
  - Dispatch is refused while `document_parsed` is False — clicking send
  during attachment parsing triggers Qwen's parse toast or bot
  verification (`SendDispatchError`).
  - An acknowledgment is a real new user turn (message count growth,
  user-bubble growth, or changed latest text); a cleared composer or
  disabled button is not evidence.
  - A parse toast appearing after the click holds the dispatch loop
  until parsing finishes rather than re-sending into it.
  - Enter is the keyboard fallback when the send button never clicks.
  - Missing lifecycle emitter is refused before any DOM work
  (`QwenCliError`).
- **Edge Cases**: A page that resets the composer without committing the
turn does not acknowledge; the wait times out and reports a dispatch
failure instead of falsely succeeding.
- **Error Handling**: A control that never clicks (with fallback
disabled), or a click that never acknowledges, surfaces
`SendDispatchError` carrying the reason.

### FR-RUNTIME-003: Watch the response stream

- **Description**: Follow the response stream until a stable terminal
state is reached, the stall detector fires, or the ceiling elapses.
- **Input**: A runtime request with verb `watch`, the live page, the
response timeout, the message count before dispatch, the lifecycle
emitter, and the optional streamer configuration (polling interval,
stability checks, minimum text length) plus an optional cancel token.
- **Output**: The runtime response carrying the stable response text and
the extraction verdict (`response_text`, `verdict`).
- **Business Rules**:
  - The extraction verdict is `complete` on a terminal, validated,
  stable response (`StreamVerdict`); the `stalled` and `incomplete`
  outcomes that the prompt adapters derive from the monitor's exceptions
  are the FR-PROMPT-006 verdicts — this feature produces them, the
  prompt feature reports them.
  - `timeout_sec` is a hard wall-clock cutoff, not an idle budget: a
  long thinking phase consumes it (`ResponseDetectionTimeoutError`).
  - The stall detector is event-driven (no forward event — thinking,
  text change, completion — inside the stall window) and raises
  `StuckDetectedError`, which is terminal for the run.
  - A set cancel token raises `RunCancelledError` before and during the
  wait so only the owning run stops.
  - Response content is validated before `complete` is claimed
  (empty/challenge/error pages never pass as answers).
  - Missing lifecycle emitter is refused before any DOM work
  (`QwenCliError`).
- **Edge Cases**: A stream that emits no forward event for the full
stall window reports `stalled` (partial saved by the prompt feature);
a hard ceiling crossing reports `incomplete`.
- **Error Handling**: Safety circuit breaker
  (`safety_timeout_sec`) answers a timeout error instead of polling
  forever; a non-dict page probe is recovered by falling back to the
  tiered reader for that poll only.

### FR-RUNTIME-004: Upload an attachment

- **Description**: Validate an attachment file against the locked
allowlist and byte ceiling, then attach it to the page and wait for both
backend parse and DOM parse readiness.
- **Input**: A runtime request with verb `upload`, the live page, the
file path, the optional lifecycle emitter, and the `web_loaded` gate.
- **Output**: The runtime response carrying the acceptance verdict
  (`accepted`).
- **Business Rules**:
  - Pre-flight runs before any browser work: extension allowlist, zero-
  byte rejection, and the exact byte ceiling of
  `104857600` bytes (`100 * 1024 * 1024`) — a strictly-over file is
  rejected with the limit named, a file exactly at the ceiling passes.
  - Upload is refused while `web_loaded` is False (`RuntimeError`) —
  the page must be ready before the chooser opens.
  - Attachment-card presence is verified by filename match across the
  configured selector families in one `page.evaluate` probe per poll.
  - Document parse is dual-gated: the backend `/files/parse` completion
  and a DOM readiness pass (no toast, no pending spinner) both must
  clear before the capability reports accepted.
- **Edge Cases**: A file that validates but never renders a card
surfaces a timeout naming the file; transient Playwright errors during
the card poll are retried within the deadline, while a card-shaped parse
answer of the wrong type is a contract violation.
- **Error Handling**: A pre-flight failure returns not-accepted
(`accepted=False`); a card or parse timeout returns not-accepted with
the reason logged; a web-not-loaded gate raises.

### FR-RUNTIME-005: Persist the response artifact

- **Description**: Write the response text to the operator's named
destination with a run-traceability `.meta.json` sidecar.
- **Input**: A runtime request with verb `persist`, the output path, the
response content, the run context, the source file, duration and
character counts, plus the optional saver configuration.
- **Output**: The runtime response carrying the saved path and the
written text (`saved_path`, `response_text`).
- **Business Rules**:
  - The artifact is written `0o600` (owner read/write only) on both the
  atomic and direct paths (Issue #353).
  - The `.meta.json` sidecar lands under the XDG metadata directory
  (`DEFAULT_METADATA_DIR` by default), never beside the output; the
  output directory holds only response artifacts (FR-PROMPT-009).
  - A directory destination gets a generated collision-free name
  (`qwen_output_<timestamp>_<run-id>[-n].md`) reserved by exclusive
  create; an explicitly named file is honored exactly as written and
  overwritten in place.
  - The sidecar is mandatory traceability: its failure raises after the
  main artifact is safely on disk so the artifact stays inspectable.
  - A missing `output_path` is refused before any write
  (`QwenCliError`).
- **Edge Cases**: A run without its own context defaults to a fresh run
context; UI noise (thinker/app chrome markers) is stripped from the
content before the write.
- **Error Handling**: A write failure surfaces `OutputWriteError`
naming the path, and a reserved-but-empty name is released so the next
attempt does not skip a suffix for a zero-byte husk.

### FR-RUNTIME-006: Route any runtime verb through one aggregate door

- **Description**: `IPromptRuntimeAggregate.execute` is the single door
over the five capabilities: one request verb selects exactly one
capability method, so no surface branches on verbs itself.
- **Input**: A runtime request naming one of `inject`, `send`, `watch`,
`upload`, `persist` plus that verb's fields.
- **Output**: The runtime response shaped by the routed verb: turn
count (`send`), text + verdict (`watch`), acceptance (`upload`), saved
path + text (`persist`), default (`inject`).
- **Business Rules**:
  - A verb is added as a `RuntimeRequest` variant, never as a second
  aggregate method.
  - A verb outside the five (or one added to `RuntimeVerb` without a
  wired capability) raises `QwenCliError` naming the verb.
  - A verb called with a missing required slot (`emitter` for
  `send`/`watch`, `filepath` for `upload`, `output_path` for `persist`)
  raises `QwenCliError` naming the slot instead of failing deep in the
  capability.
  - The agent imports only shared contracts, taxonomy, and utility —
  never a runtime capability module, never a surface (AES201/AES405).
- **Edge Cases**: Two consumers holding the same aggregate see one
routing behaviour; per-verb differences live in the request fields, not
in the door's shape.
- **Error Handling**: Every refusal above surfaces `QwenCliError` with
the configuration defect named, so a wiring bug fails at the door.

## API Contract

### Protocol API

Each row is one method on one of the feature's six protocol seam classes; the class is named in the Description column.

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `find_input` | page, injector config | the input element | element not found | none | Locate the chat input. (IRuntimeInjectProtocol, FR-RUNTIME-001) |
| `inject_text` | page, prompt text, injector config | none | element not found, injection error | prompt injected | Inject prompt text via multi-strategy DOM injection. (IRuntimeInjectProtocol, FR-RUNTIME-001) |
| `click_send` | page, lifecycle emitter, sender config, document-parsed gate | none | send dispatch error | send clicked | Trigger the send action. (IRuntimeSendProtocol, FR-RUNTIME-002) |
| `count_messages` | page | chat turn count | none | none | Count chat turns after dispatch. (IRuntimeSendProtocol, FR-RUNTIME-002) |
| `latest_message_text` | page | response text | none | none | Return the latest assistant response text. (IRuntimeSendProtocol, FR-RUNTIME-002) |
| `wait_for_response` | page, response timeout, turn count before dispatch, emitter, streamer config, cancel token | stable response text + extraction verdict | stream error, run cancelled | generation finished | Wait for a stable assistant response. (IRuntimeWatchProtocol, FR-RUNTIME-003) |
| `is_generation_complete` | page | generation flag | none | none | True when Qwen has finished generating. (IRuntimeWatchProtocol, FR-RUNTIME-003) |
| `is_thinking_active` | page | thinking flag | none | none | True when Qwen is thinking or streaming. (IRuntimeWatchProtocol, FR-RUNTIME-003) |
| `upload_attachment` | page, file path, emitter, web-ready gate | accepted flag | upload error, web-not-loaded gate | file uploaded | Attach a file as an attachment. (IRuntimeUploadProtocol, FR-RUNTIME-004) |
| `validate_file` | file path, max size bytes | file size in bytes | file error | none | Pre-flight validation against the allowlist and byte ceiling. (IRuntimeUploadProtocol, FR-RUNTIME-004) |
| `write_output` | output path, content, run context, source file, duration, character counts, saver config | none | output write error | output copied | Write the artifact and its `.meta.json` sidecar. (IRuntimePersistProtocol, FR-RUNTIME-005) |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | runtime request naming one verb plus that verb's fields | runtime response shaped by the verb: turn count (`send`), text + verdict (`watch`), acceptance (`upload`), saved path + text (`persist`), default (`inject`) | `QwenCliError` for an unknown verb or a missing required slot | varies by verb | Single composite entry point over the five capability seams. (IRuntimeDoorProtocol / IPromptRuntimeAggregate, FR-RUNTIME-006) |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Prompt shared-flow orchestrator | in | Drives the inject → send → wait → save ordering through these seams | a capability failure -> surfaced as the flow's prompt failure |
| Surfaces and root container | in | Hold the aggregate and route one runtime verb | unknown verb or missing slot -> `QwenCliError` at the door |
| Playwright page (live browser session) | out | DOM effects for inject, send, watch, upload | missing input or control -> element-not-found / dispatch error at the seam |
| Output filesystem + XDG metadata directory | out | Artifact at the named destination, `.meta.json` under the metadata dir | write failure -> output write error naming the path |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Attachment pre-flight ceiling | exactly `104857600` bytes (`100 * 1024 * 1024`); a strictly-over file fails before any browser work | boundary test at the exact byte limit |
| Artifact permissions | `0o600` (owner read/write only) on every write path | mode check on a persisted artifact after a real write |
| Sidecar placement | `.meta.json` lands under the metadata directory, never beside the artifact | path assertion on the sidecar after a real write |
| Door refusal | unknown verb or missing required slot raises `QwenCliError` before any capability runs | call the door with a bad request and assert the raised reason |
| Smoke boot-to-persist | aggregate boots and writes one artifact in well under five seconds | timed smoke test through the door |

## Test Scenarios

- The aggregate boots over the five real capabilities and routes a verb.
- A verb outside the runtime set is refused by name.
- A persisted response is `0o600` on disk.
- The `.meta.json` sidecar lands in the metadata dir, never beside the artifact.
- An attachment over 104857600 bytes is rejected pre-flight; one exactly at the ceiling passes.
- `persist` writes the artifact and its sidecar to a real temporary directory.
- A completed stream reports the stable text and a `complete` verdict through the door.
- A `send`/`watch` without an emitter, an `upload` without a file, and a `persist` without a destination are refused at the door.
- The full runtime lifecycle runs through one door end to end (upload → inject → send → watch → persist).
- The aggregate boots and persists one artifact in well under five seconds.

## Assumptions & Constraints

- The five capability seams are declared by the prompt feature in the shared contract kernel; this feature's seam traits extend them, so one capability class satisfies both features.
- The inject → send → wait → save ordering belongs to the prompt feature's shared flow dispatcher; re-sequencing it here is out of scope by design.
- The DOM selectors the injector and stream monitor match are pinned by regression tests; changing them is a deliberate, reviewed change.
- The `104857600`-byte ceiling and the extension allowlist are locked product values; boundary changes are a reviewed change.

## Glossary

- **Runtime verb**: One of `inject`, `send`, `watch`, `upload`, `persist` — the request variant that selects exactly one capability seam.
- **Aggregate door**: The single `execute` entry point of the runtime aggregate; a verb is added as a request variant, never as a second method.
- **Seam**: One capability's contract trait: one abstract class, one FR.
- **Extraction verdict**: The watch outcome — complete, stalled, or incomplete — as FR-PROMPT-006 defines it.
- **Sidecar**: The `.meta.json` run-traceability file that lands under the XDG metadata directory beside neither the artifact nor the output folder.
