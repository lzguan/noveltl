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
Polling, recovery dispatch, and exitpoint state transitions remain separate work.
