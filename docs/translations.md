# Translation stage artifact contract

Normalized stage artifacts use JSONL records keyed by `TranslationDataKey`
(`backend/src/translations/types.py`). Every key contains:

- `chapter_id`: the source chapter UUID from the job's chapter associations.
- `data_name`: the component type, currently `chapter` or `memories`.

The owning task and its file reference supply job, batch, and stage scope.
Those identifiers do not need to be repeated in each record. A key identifies
one complete component: chapter text or a collection of memories. An empty
memory collection is a present component; a missing record is not.

## Producer requirements

Before publishing a completed stage output, validate that:

- Every chapter ID belongs to the task's batch.
- Every `(chapter_id, data_name)` key is unique within the artifact.
- For every chapter in the batch, the component set equals the action
  signature's `output_types`: no missing or unexpected components.
- Each payload is valid for its declared `data_name`.

Record ordering carries no meaning. If multiple inference requests contribute
to a component, the action assembles their results before publishing that
component. Model calls and carried-forward data are both subject to the same
output contract.

## Consumer requirements

The next stage reads the preceding task's completed output for the same batch
and selects components by chapter ID and its action's `input_types`. Extra
components produced by the preceding action may be ignored; required components
must be present. The first stage builds its required components from the job's
pinned source revisions and configured memory retrieval.

An action may explicitly attach data outside its declared inputs, as
`combine_chapter` does when attaching the pinned source chapter to memories.
Such behavior belongs to that action's implementation, rather than implicit
fallback to arbitrary earlier stage outputs.

## Provider boundary and implementation status

Provider request keys identify individual inference calls and may include
request or chunk identifiers. `BatchLineCodec[KeyT]` remains generic; it does
not require request keys to equal stored component keys. Provider input JSONL
also follows the provider's format, rather than this normalized artifact contract.

The key and record types are implemented in `backend/src/translations/types.py`
and `backend/src/translations/records.py`. Each line contains `chapter_id`,
`data_name`, and `payload`. `TranslationRecord` discriminates on `data_name`:

- `chapter`: the payload is the complete chapter text as a string.
- `memories`: the payload is a list of snapshots using the existing `Memory`
  schema, whose `plugin_name` identifies the owning plugin. The shared record
  format does not include plugin-specific fields such as glossary terms.

The same record schemas apply to the initial canonical artifact and each task's
normalized output. They do not describe `input_file_id`, which holds vendor JSONL.
Record keys are available through the non-serialized `key` property.

`jsonl.encode_translation_record(record)` emits UTF-8 JSON and a trailing newline,
retaining Python field names, including in reused memory schemas.
`jsonl.iter_translation_records(chunks)` reads arbitrary byte chunks and validates
each record. It accepts CRLF and a final record without a newline, rejects blank
or malformed lines, and propagates download errors. Empty streams yield no records.
`validation.validate_output_records(records, chapter_ids=..., output_types=...)`
checks chapter membership, component types, unique keys, and completeness while
yielding records. It retains only keys. Callers must exhaust it inside the upload
context before publishing the artifact, since missing components raise an error
only at exhaustion. Source errors propagate to the caller.

## Callback claims

`new_func(expect=..., during=..., finish=..., lease_seconds=300)` registers a
callback receiving `ActionTaskContext`; the queued callable still receives only
the task UUID. The wrapper commits a claim token and expiry before running the
callback, then commits callback writes and the `finish` state before dispatch.
An active claim, failed task, or incompatible state prevents execution. Expired
claims in the declared `during` state can be replaced by a fresh token.

Callbacks can mutate their task's output fields and use `context.db`. The wrapper
owns status, failure, and claim fields, as well as commit/rollback. Exceptions
roll back callback writes; a still-owned, unexpired claim records `failed_at` and
`error`, retaining the `during` state and clearing the claim. Lost owners cannot
commit completion or record failure over a replacement worker.

Renewal is cooperative, following the memory worker's pattern. Call
`context.renew_lease()` between units of long work, before expiry. It uses a fresh
transaction, so call it before flushing or locking the task row in the callback
session. Choose a lease long enough for the longest individual blocking operation.
There is no background heartbeat. Completion checks database wall-clock time,
not the callback transaction's start time.

These claims fence database completion, not external provider/S3 side effects.
Exitpoint requires the current task to be complete and not failed. It marks the
next task in the same batch READY, commits, then dispatches that action's
entrypoint. Retrying exitpoint can redispatch an already-ready task after a queue
failure; it does not reset running, completed, claimed, or failed tasks.

`new_poll` accepts the same state/lease parameters plus `interval_seconds`.
Its callback returns `False` while pending: the wrapper restores `expect`,
releases the claim, commits, and queues the same callback with a countdown.
Returning `True` commits `finish` and dispatches the next callback. Exceptions
use the same failure handling as `new_func`. Workers do not wait between polls.
Recovery dispatch remains separate work.

## Plain translation preparation

`actions.translate.prepare` is a module-level callback decorated with
`callbacks.new_func`. Its module constructs one `CeleryActionCallbacks` instance.
At execution time, preparation resolves the codec from the stage's model, obtains
the store through `files.dependencies.get_object_store`, and reads storage name
and bucket from file settings. Submission and polling follow preparation.

The translation Celery app includes `src.translations.actions` during worker
startup. That package imports the action modules, then populates the shared
`actions.registry.ACTION_CALLBACKS` dictionary. Registration does not create an
S3 client or perform database/network calls. The broker uses
`TRANSLATIONS_DATABASE` (default Redis database 4), separately from other workers.

The stage uses `TranslateConfig`: an explicit model name, a target language
(English by default), optional instructions, temperature, and maximum output
tokens. Job creation stores this typed config as JSON.

On the first stage, preparation reads pinned chapter-content revisions directly.
On subsequent stages, it requires the previous task's complete normalized output,
validates that artifact, and selects its chapter records. No initial artifact is
required. Each chapter becomes one provider-neutral inference request with a
`TranslationDataKey`; only the resolved codec handles vendor formatting.

The encoded requests are written incrementally to a temporary file, then uploaded
through the existing readable-file accessor. Successful preparation stores
`input_file_id` and transitions to PREPARED through the claim wrapper. It does not
write `output_file_id` or submit a provider job.

`submit` claims PREPARED as SUBMITTING, streams the stored vendor input through
`BatchJobClient.create_batch_job`, then stores `provider_batch_id` and commits
PROCESSING before dispatching `poll`. Client factories are injected through
`dependencies.BATCH_CLIENT_FACTORIES`, keyed by model. No concrete provider
client is registered yet.

`poll` checks the saved provider ID once. Pending jobs reschedule after 60 seconds;
completion saves `provider_output_id` and transitions to PROCESSED. Provider
failures and transport exceptions record failure without automatic retry.
`finalize` claims PROCESSED as FINALIZING, downloads the provider output, frames
its byte chunks into JSONL lines, and decodes them with the configured codec.
Every successful chapter becomes a normalized `ChapterRecord`. Failed items,
malformed records, unexpected keys, duplicates, and missing chapters fail the
task without publishing an output file reference. Validated records are written
incrementally to a temporary file before uploading through the file accessor.
Only after upload succeeds does the wrapper commit `output_file_id` and COMPLETE,
then invoke exitpoint to ready and dispatch the next stage for this batch.
Download/upload failures retain FINALIZING with failure details; after recovery
clears the failure, finalization can restart without resubmitting inference.

Submission is not exactly-once: a provider may accept a job before the worker
loses its response or database commit. SUBMITTING identifies that ambiguous
step, but retrying an expired submission can create another provider job.
Provider idempotency/reconciliation and recovery endpoints remain future work.

## Chapter combination

`actions.combine_chapter.combine` is a deterministic callback registered at worker
startup. It transitions READY → FINALIZING → COMPLETE in one claimed invocation.
It requires the immediately preceding stage's completed output for the same batch,
validates that stage's full output signature, and preserves its memory records.
It attaches chapter text from the job's pinned source revisions, ignoring any
chapter text in the previous output. The combined artifact must contain exactly
one chapter and one memories record per batch chapter before it is uploaded.
Successful completion stores `output_file_id` and advances via the shared exitpoint.
No provider job or input file is created. First-stage memory retrieval is not
implemented; using this action as stage zero fails explicitly.

## OpenAI-compatible chat codec

`codecs.openai_chat.OpenAIChatBatchCodec[KeyT]` implements `BatchLineCodec` for
the [Chat Completions batch format](https://developers.openai.com/api/docs/guides/batch).
Construct it with `TypeAdapter(TranslationDataKey)` for translation components,
or another Pydantic key adapter for other request keys. The key is serialized as
JSON inside `custom_id`; decoding needs no in-memory request mapping.

The codec emits one UTF-8 JSONL request for `/v1/chat/completions` and reads one
complete result line. It handles batch errors, HTTP/API errors, and refusals.
Non-`stop` completions (including truncation) return item failures; malformed
records raise `ValueError`. Successful results retain text and finish reason.

`max_output_tokens` maps to `max_completion_tokens` by default. Set
`max_tokens_field="max_tokens"` for compatible backends that require that field.
Model capabilities, provider limits, transport, and registry lookup remain outside
this codec. It does not implement the Responses API.

## Codec selection

`ModelName` currently supports `qwen-plus` and `qwen-flash`, both listed in
[Model Studio's batch documentation](https://www.alibabacloud.com/help/en/model-studio/batch-inference).
`TranslateConfig.model` validates this selection before job creation.

`codecs.registry.MODEL_CODECS` maps those model names directly to factories for
`OpenAIChatBatchCodec[TranslationDataKey]`, configured to use `max_tokens`.
`get_codec(model)` creates a fresh instance. No codec-name indirection or
environment mapping is needed. To add a model, extend `ModelName` and this mapping.
Preparation resolves the codec at execution time; transport uses a separate
injected client factory for the same model.
