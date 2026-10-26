# PROMPT_RUNTIME Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The prompt runtime feature is the browser/stream layer of the prompt feature.
It drives the live Playwright page: it injects prompt text, clicks the send
control, follows the response stream until a terminal state, uploads
attachments, and persists the extracted response. It is composed into the
prompt pipeline by `modules/prompt` through the prompt protocol contracts in
the shared kernel; the verb routing and cancellation logic stay in
`modules/prompt`.

## Functional Requirements

This document is a **view** of [modules/prompt/FRD.md](../prompt/FRD.md) — the
authoritative spec for the whole prompt feature — covering only the
requirements owned by the browser/stream layer; the orchestration
requirements stay there. Each entry below references that FR by ID.

### FR-PROMPT-006: Monitor the response stream

- **Description**: Follow the response stream until a terminal state is reached or the stall detector fires.
- **Input**: The live page, the stream's selectors, and the configured ceilings.
- **Output**: The extraction verdict: complete, stalled, or incomplete.
- **Business Rules**: The event-driven stall detector fires before the wall-clock response ceiling; stalled and incomplete verdicts are distinguished so a caller can decide whether to retry.
- **Edge Cases**: A stream that emits no forward event for the full ceiling reports `stalled`, not `complete`.
- **Error Handling**: A monitor that cannot read the stream reports the extraction `incomplete` rather than raising into the caller.
- **Authoritative text**: [FR-PROMPT-006](../prompt/FRD.md#fr-prompt-006-monitor-the-response-stream).

### FR-PROMPT-007: Inject prompt text into the chat

- **Description**: Locate the chat input and inject the prompt text via multi-strategy DOM injection.
- **Input**: A page, the prompt text, and the optional injector configuration.
- **Output**: The input element that received the text, or a not-found error.
- **Business Rules**: The input element must exist before injection; a missing input is a hard error.
- **Edge Cases**: A chat that has not loaded reports a not-found error for the input element.
- **Error Handling**: A not-found input surfaces an element-not-found error naming the selector.
- **Authoritative text**: [FR-PROMPT-007](../prompt/FRD.md#fr-prompt-007-inject-prompt-text-into-the-chat).

### FR-PROMPT-008: Trigger the send action

- **Description**: Click the send control and count the chat turns that result.
- **Input**: A page, a lifecycle emitter, and the optional send configuration.
- **Output**: The number of chat turns after the send, and the latest assistant text.
- **Business Rules**: The send control must be clickable; a disabled control is a hard error.
- **Edge Cases**: A send that produces no new turn is reported as a dispatch failure.
- **Error Handling**: A send that fails surfaces a send-dispatch error carrying the reason.
- **Authoritative text**: [FR-PROMPT-008](../prompt/FRD.md#fr-prompt-008-trigger-the-send-action).

### FR-PROMPT-009: Save the response to the operator's destination

- **Description**: Persist the processed response; the run-traceability sidecar goes to the XDG state metadata directory, never the output directory.
- **Input**: The output path, the response text, the run context, the source file, duration, and character counts.
- **Output**: A written response file at the named destination, plus a `.meta.json` sidecar under `DEFAULT_METADATA_DIR` mirroring the artifact's path relative to the output root.
- **Business Rules**: The output path must be writable; a non-writable path is a hard error. The output directory holds only prompt responses.
- **Edge Cases**: A mid-stream extraction failure keeps the response file so an operator can inspect it.
- **Error Handling**: A write failure surfaces an output-write error naming the path.
- **Authoritative text**: [FR-PROMPT-009](../prompt/FRD.md#fr-prompt-009-save-the-response-to-the-operators-destination).

### FR-PROMPT-010: Upload an attachment

- **Description**: Attach a file to the chat as an attachment, with pre-flight validation.
- **Input**: A page, the file path, the optional upload configuration, and the optional lifecycle emitter.
- **Output**: A boolean indicating whether the attachment was accepted.
- **Business Rules**: A file exceeding the upload limit is rejected with the limit named; the byte ceiling is exactly `104857600` bytes (`100 * 1024 * 1024`).
- **Edge Cases**: A file that cannot be read surfaces a file error naming the path.
- **Error Handling**: An upload failure surfaces an upload-failure error carrying the reason.
- **Authoritative text**: [FR-PROMPT-010](../prompt/FRD.md#fr-prompt-010-upload-an-attachment).

## API Contract

The protocol contracts this layer implements live in the prompt protocol
contracts of the shared kernel.

### Protocol API

The browser/stream layer owns `IStreamProtocol`, `IInjectionProtocol`,
`ISendProtocol`, `IUploadProtocol`, and `ISaverProtocol`. The full method
table lives in the authoritative FRD.

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `wait_for_response` | page, timeout, msg_count_before, emitter, config, cancel_event | response text + `extraction_verdict` | stream error, run cancelled | generation finished | Wait for a stable assistant response. (IStreamProtocol) |
| `is_generation_complete` | page | generation flag | none | none | True when Qwen has finished generating. (IStreamProtocol) |
| `is_thinking_active` | page | thinking flag | none | none | True when Qwen is currently thinking/streaming. (IStreamProtocol) |
| `find_input` | page, config | input element | element not found | none | Locate the chat input element. (IInjectionProtocol) |
| `inject_text` | page, text, config | none | element not found | prompt injected | Inject prompt text via multi-strategy DOM injection. (IInjectionProtocol) |
| `click_send` | page, emitter, config, document_parsed | none | send dispatch error | send clicked | Trigger the send action. (ISendProtocol) |
| `count_messages` | page | chat turn count | none | none | Count chat turns. (ISendProtocol) |
| `latest_message_text` | page | response text | none | none | Return the latest assistant response text. (ISendProtocol) |
| `upload_attachment` | page, filepath, emitter, web_loaded | accepted flag | upload error | file uploaded | Attach a file as an attachment. (IUploadProtocol) |
| `validate_file` | filepath, max_size_bytes | file size in bytes | file error | none | Pre-flight validation of an attachment. (IUploadProtocol) |
| `write_output` | path, content, ctx, src, dur, input_chars, output_chars, config | none | output write error | output copied | Write processed output with metadata header + sidecar. (ISaverProtocol) |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| none | — | — | — | — | This module carries no aggregate; `modules/prompt` composes these protocols into the prompt pipeline. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| `modules/prompt` flow dispatcher | in | Drive one send and follow its stream | stream error -> the attempt is retriable within the dispatch retry budget |
| Browser aggregate | out | Obtain the authenticated live page per run | authentication error -> the run fails before the send |
| Output filesystem | out | Persist the response and its metadata sidecar | output write error -> the failure names the path |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Stream stall detection | every stalled stream reports `stalled`, not complete | injection of a stream that emits no forward event |
| Response save | every completed run writes the response file | file presence after a completed run |
| Attachment ceiling | an over-limit attachment is rejected pre-flight, before any browser launch | upload validation against the exact byte limit |

## Test Scenarios

- A stalled stream reports `stalled` (and saves the partial) and does not retry the send.
- A hard response timeout reports `incomplete` (and saves the partial).
- An attachment exceeding the upload limit is rejected with the limit named.
- A response file survives a mid-stream extraction failure so an operator can inspect it.

## Assumptions & Constraints

- The DOM selectors the stream monitor matches are pinned by regression tests; changing them is a deliberate, reviewed change.
- The runtime layer carries no verb routing or cancellation logic; those stay in `modules/prompt`.

## Glossary

- **Stream monitor**: The seam that follows the response until a terminal state.
- **Stall detector**: The check that distinguishes a slow response from a wedged one. Event-driven and retriable; may fire before the response ceiling.
- **Response ceiling**: The absolute, terminal wall-clock bound (`request_timeout`) for one dispatch attempt.
- **Extraction verdict**: The result of the monitor: complete, stalled, or incomplete.
- **Output sidecar**: The `.meta.json` traceability file written under the XDG state metadata directory, never the output directory.
