# PROMPT Functional Requirements Document

## Feature Overview

The prompt feature drives one prompt through the authenticated chat: it injects the prompt, attaches any attachment, sends it, follows the stream until a terminal state, and saves the response. One orchestrator routes each prompt verb to the adapter that serves it, and the shared-flow orchestrator drives the inject, dispatch, monitor, and save steps so the surfaces and job runners see one pipeline.

## Functional Requirements

### FR-PROMPT-001: Run a direct prompt

**Description:**

Send a text prompt to the live chat and save the response.

#### Business Logic

- An empty prompt is rejected at the surface, so an adapter never receives an empty text.
- The response is saved to the operator's named output destination.

#### Edge Cases

- A response the stream never stops emitting is cut off at the configured stall detector and reported as `stalled` (partial saved); a hard wall-clock response timeout is reported as `incomplete`.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A prompt request carrying the text, the run configuration, and the optional output path. |
| **Output** | A prompt response carrying the saved path and the extraction verdict. |
| **Protocol** | `IDirectPromptProtocol` — one of the prompt protocol seam classes. |
| **Method** | `process_direct_prompt` |
| **Event** | `generation_finished` — emitted when the stream reaches a terminal state. |
| **Error** | A send that fails surfaces a prompt failure carrying the reason; the run records a failure outcome in metrics. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A direct prompt with a live chat | The pipeline runs | A response file is produced at the named destination |

#### Metric

| Target Metric | Value |
| --- | --- |
| Direct-prompt response save rate | 100% |

### FR-PROMPT-002: Run a file prompt

**Description:**

Send the contents of a prompt file through the pipeline.

#### Business Logic

- The file must exist and be readable before the pipeline starts.

#### Edge Cases

- A file that cannot be read surfaces a file error naming the path.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A prompt request naming the file path, the run configuration, and the optional output path. |
| **Output** | A prompt response carrying the saved path and the extraction verdict. |
| **Protocol** | `IPromptFileProtocol` — one of the prompt protocol seam classes. |
| **Method** | `process_prompt_file_only` |
| **Event** | `generation_finished` — emitted when the stream reaches a terminal state. |
| **Error** | A pipeline failure mid-stream surfaces the failure reason and keeps the response file, so an interrupted extraction is inspectable. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A readable prompt file | The pipeline runs | A response file is produced at the named destination |

#### Metric

| Target Metric | Value |
| --- | --- |
| File-prompt response save rate | 100% |

### FR-PROMPT-003: Run an attachment prompt

**Description:**

Send a prompt with one attached file.

#### Business Logic

- The attachment must satisfy the Product-approved format and exact-byte size matrix linked to F-003; each rejected boundary case has a specified validation stage and stable failure reason.
- The byte ceiling is exactly `104857600` bytes, not a mixed MB/MiB limit.
- The supported extension allowlist is enforced by the shared validation utility; unsupported or mismatched content is rejected at pre-flight, before any browser launch.
- An attachment that uploads but fails mid-stream still reports the response file when the extraction recovers.

#### Edge Cases

- An attachment that exceeds the upload ceiling is rejected at pre-flight validation with the exact byte limit named; zero-byte, unsupported-format, unreadable, and type/content-mismatch inputs each fail at the specified stage with a stable reason and no accidental provider submission.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A prompt request naming the prompt text, the attachment path, the run configuration, and the optional output path. |
| **Output** | A prompt response carrying the saved path and the extraction verdict. |
| **Protocol** | `IAttachmentPromptProtocol` — one of the prompt protocol seam classes. |
| **Method** | `process_prompt_with_attachment` |
| **Event** | `generation_finished` — emitted when the stream reaches a terminal state. |
| **Error** | An attachment failure surfaces an upload error naming the file; the pipeline does not retry the send. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An attachment over the upload limit | The pipeline runs | The attachment is rejected at pre-flight with the limit named |

#### Metric

| Target Metric | Value |
| --- | --- |
| Pre-flight rejection of over-ceiling attachments | 100% |

### FR-PROMPT-004: Cancel a running prompt

**Description:**

Stop the file and attachment pipelines a run owns.

#### Business Logic

- A direct prompt has no cancel registry, so cancel reports zero pipelines stopped for it.
- A pipeline that already reached a terminal state is not reported as stopped.

#### Edge Cases

- A cancel on a run with no active pipeline reports zero.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A cancel request naming the run-scoped cancel event. |
| **Output** | The number of pipelines that stopped. |
| **Protocol** | `IPromptFileProtocol` / `IAttachmentPromptProtocol` — the cancel path of the prompt protocol seam classes. |
| **Method** | `request_cancel` |
| **Event** | none |
| **Error** | A cancel whose event is not registered surfaces no error; the pipeline was already terminal. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A cancel on a terminal pipeline | The cancel runs | Zero pipelines are reported stopped |

#### Metric

| Target Metric | Value |
| --- | --- |
| Cancel correctness (no false stops) | 100% |

### FR-PROMPT-005: Targeted run cancellation

**Description:**

Maintain a thread-safe registry of in-flight runs so a cancel stops exactly one run's browser context without touching sibling runs on the same instance.

#### Business Logic

- Entries are keyed by the stable run ID, never by the object identity of a cancel event, so a cancel targets one specific run even when events are recreated across threads.
- A private event index supports the cancel-by-event convenience path used by surfaces that hold only the original event.
- Cancelling a run sets its cancel event so any in-progress flow check observes the new state, and closes its live browser context so the underlying browser process stops.

#### Edge Cases

- A cancel for a run that already finished is a no-op; a run whose browser context is already gone still sets the event.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A run-scoped cancel state carrying the stable run ID and an optional cancel event. |
| **Output** | The registered verdict, the released verdict, or the cancelled verdict. |
| **Protocol** | `IRunCancelProtocol` — one of the prompt protocol seam classes. |
| **Method** | `register`, `release`, `cancel_run`, `cancel_by_event` |
| **Event** | none |
| **Error** | No error is raised; a missing run is a silent no-op. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A cancel targeting one run among siblings | The cancel runs | Only the targeted run stops; siblings are untouched |

#### Metric

| Target Metric | Value |
| --- | --- |
| Targeted-cancel isolation | 100% |

### FR-PROMPT-006: Monitor the response stream

**Description:**

Follow the response stream until a terminal state is reached or the stall detector fires.

#### Business Logic

- The wall-clock response ceiling is a ceiling, not an idle budget; a long thinking phase emits no forward event, so a short ceiling aborts healthy runs.
- A stalled stream is distinguished from a complete one so a caller can decide whether to retry.
- Precedence: the event-driven stall detector may fire before the response ceiling and is retriable via the dispatch retry budget; the response ceiling is absolute and terminal for the attempt.

#### Edge Cases

- A stream that emits no forward event for the full ceiling reports `stalled`, not complete; a slow-but-emitting stream outlives the stall threshold and is only bounded by the response ceiling.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The live page, the stream's selectors, and the configured ceilings. |
| **Output** | The extraction verdict: complete, stalled, or incomplete. |
| **Protocol** | `IStreamProtocol` — one of the prompt protocol seam classes. |
| **Method** | `wait_for_response`, `is_generation_complete`, `is_thinking_active` |
| **Event** | `generation_finished` — emitted when the stream reaches a terminal state. |
| **Error** | A monitor that cannot read the stream reports the extraction incomplete rather than raising into the caller. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A stream that emits no forward event for the full stall window | The monitor runs | The verdict is `stalled` |

#### Metric

| Target Metric | Value |
| --- | --- |
| Stalled-stream detection accuracy | 100% |

### FR-PROMPT-007: Inject prompt text into the chat

**Description:**

Locate the chat input and inject the prompt text via multi-strategy DOM injection.

#### Business Logic

- The input element must exist before injection; a missing input is a hard error.

#### Edge Cases

- A chat that has not loaded reports a not-found error for the input element.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A page, the prompt text, and the optional injector configuration. |
| **Output** | The input element that received the text, or a not-found error. |
| **Protocol** | `IInjectionProtocol` — one of the prompt protocol seam classes. |
| **Method** | `find_input`, `inject_text` |
| **Event** | `prompt_injected` — emitted after the injection verifies the value landed. |
| **Error** | A not-found input surfaces an element-not-found error naming the selector. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| Prompt text is injected via the shared injection seam | The live page is driven | The input element's value matches the injected text |

#### Metric

| Target Metric | Value |
| --- | --- |
| Injection verification pass rate | 100% |

### FR-PROMPT-008: Trigger the send action

**Description:**

Click the send control and count the chat turns that result.

#### Business Logic

- The send control must be clickable; a disabled control is a hard error.

#### Edge Cases

- A send that produces no new turn is reported as a dispatch failure.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A page, a lifecycle emitter, and the optional send configuration. |
| **Output** | The number of chat turns after the send, and the latest assistant text. |
| **Protocol** | `ISendProtocol` — one of the prompt protocol seam classes. |
| **Method** | `click_send`, `count_messages`, `latest_message_text` |
| **Event** | `send_clicked` — emitted after an acknowledgment is observed. |
| **Error** | A send that fails surfaces a send-dispatch error carrying the reason. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| The send control is clicked on the live page | The pipeline runs | The turn count grows by one |

#### Metric

| Target Metric | Value |
| --- | --- |
| Send ACK pass rate | 100% |

### FR-PROMPT-009: Save the response to the operator's destination

**Description:**

Persist the processed response; the run-traceability sidecar goes to the XDG state metadata directory, never the output directory.

#### Business Logic

- The output path must be writable; a non-writable path is a hard error.
- The output directory holds only prompt responses.

#### Edge Cases

- A mid-stream extraction failure keeps the response file so an operator can inspect it.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | The output path, the response text, the run context, the source file, duration, and character counts. |
| **Output** | A written response file at the named destination, plus a `.meta.json` sidecar under the metadata directory mirroring the artifact's path relative to the output root. |
| **Protocol** | `ISaverProtocol` — one of the prompt protocol seam classes. |
| **Method** | `write_output` |
| **Event** | `output_copied` — emitted when the artifact and sidecar are on disk. |
| **Error** | A write failure surfaces an output-write error naming the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A completed run | The saver writes | The response file lands at the named destination and the sidecar lands in the metadata dir |

#### Metric

| Target Metric | Value |
| --- | --- |
| Response save correctness | 100% |

### FR-PROMPT-010: Upload an attachment

**Description:**

Attach a file to the chat as an attachment, with pre-flight validation.

#### Business Logic

- A file exceeding the upload limit is rejected with the limit named.

#### Edge Cases

- A file that cannot be read surfaces a file error naming the path.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A page, the file path, the optional upload configuration, and the optional lifecycle emitter. |
| **Output** | A boolean indicating whether the attachment was accepted. |
| **Protocol** | `IUploadProtocol` — one of the prompt protocol seam classes. |
| **Method** | `upload_attachment`, `validate_file` |
| **Event** | `file_uploaded` — emitted when the attachment is accepted. |
| **Error** | An upload failure surfaces an upload-failure error carrying the reason. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| An attachment over the limit | Pre-flight runs | The file is rejected with the limit named |

#### Metric

| Target Metric | Value |
| --- | --- |
| Pre-flight boundary accuracy | 100% |

### FR-PROMPT-011: Compile a folder to a single markdown file

**Description:**

Compile folder contents to a single markdown file, optionally following imports.

#### Business Logic

- The folder must exist and be readable before compilation starts.

#### Edge Cases

- A folder that cannot be read surfaces a file error naming the path.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A folder path, an optional output path, a maximum recursion depth, and an import depth. |
| **Output** | The compiled markdown file path. |
| **Protocol** | `IFolderCompileProtocol` — one of the prompt protocol seam classes. |
| **Method** | `compile_folder` |
| **Event** | `document_parsed` — emitted when compilation completes. |
| **Error** | A compile failure surfaces the reason and leaves the partial output for inspection. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A readable folder | The compiler runs | A single markdown file is produced |

#### Metric

| Target Metric | Value |
| --- | --- |
| Folder compile correctness | 100% |

### FR-PROMPT-012: Resolve a folder to an attachment-ready file

**Description:**

Resolve a path to an attachment-ready file, compiling folders to markdown when needed.

#### Business Logic

- A directory is compiled to markdown before it is used as an attachment.

#### Edge Cases

- A path that is neither a file nor a folder is rejected.

#### Technical Specification

| Aspect | Detail |
| --- | --- |
| **Input** | A path, a maximum recursion depth, and an import depth. |
| **Output** | A path to an attachment-ready file. |
| **Protocol** | `IFolderToAttachmentProtocol` — one of the prompt protocol seam classes. |
| **Method** | `resolve_to_attachment`, `is_folder` |
| **Event** | none |
| **Error** | A resolution failure surfaces the reason and names the path. |

#### Test

| Context | When Action | Then Observable Result |
| --- | --- | --- |
| A directory path | The resolver runs | An attachment-ready markdown file is produced |

#### Metric

| Target Metric | Value |
| --- | --- |
| Path resolution correctness | 100% |

## Public Interface

| Aspect | Detail |
| --- | --- |
| Agent | `PromptOrchestrator` |
| Aggregate | `IPromptAggregate` |
| Method | `execute` |
| Request | `PromptRequest` — variants for direct prompt, file prompt, attachment prompt, cancel, and shared-flow verbs |
| Response | `PromptResponse` — carries the saved path, the extraction verdict, and the stopped-pipelines count for cancel |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD.md | Product requirements | [PRD.md](../../PRD.md) |
| BACKLOG.md | Task tracking, implementation status | [BACKLOG.md](BACKLOG.md) |
| ROADMAP.md | Roadmap status | [ROADMAP.md](../../ROADMAP.md) |
| ARCHITECTURE.md | Layer contract | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
