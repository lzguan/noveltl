# Chapter-translation pipeline

Code checked 2026-11-14. This is the batch chapter-translation subsystem, distinct
from the memory recording and glossary [term-naming jobs](memory-jobs.md).
Term translations and conventions can be loaded as artifact streams and consumed
as optional context by translation prompts.

## Entry points

| Responsibility | Source |
| --- | --- |
| Signature type, type inference, lifecycle states | [types.py](../../backend/src/translations/types.py) |
| Public envelope, typed stage configs and their signatures, input sources | [schemas.py](../../backend/src/translations/schemas.py) |
| Reading the previous stage, building a stage's output, storing files | [actions/common/](../../backend/src/translations/actions/common/) |
| Action discovery and form metadata | [metadata.py](../../backend/src/translations/metadata.py) |
| Job/stage/batch/task persistence and pinned chapters | [models.py](../../backend/src/translations/models.py), [tasks/jobs.py](../../backend/src/translations/tasks/jobs.py) |
| Controls and dispatch reporting | [service.py](../../backend/src/translations/service.py) |
| Worker callback contract, step specs, and wrappers | [actions.py](../../backend/src/translations/actions/actions.py), [celery_actions.py](../../backend/src/translations/actions/celery_actions.py) |
| Claimed step execution and next-stage handoff | [runner.py](../../backend/src/translations/actions/runner.py) |
| Lease ownership | [claims.py](../../backend/src/translations/tasks/claims.py) |
| Normalized data, JSONL, output completeness | [records.py](../../backend/src/translations/records.py), [jsonl.py](../../backend/src/translations/jsonl.py), [validation.py](../../backend/src/translations/validation.py) |
| Provider transport and response codecs | [clients/](../../backend/src/translations/clients/), [codecs/](../../backend/src/translations/codecs/) |
| Frontend pipeline builder and results viewer | [translations panel](../../frontend/src/edit/panels/translations/) |

## Streams, signatures, and full-state artifacts

A job's data flows as named **streams**, each with a type (`StreamType`: `chapter`,
`memories`, `terms`, `conventions`). For now a loaded stream must be named after
its type, so there is one stream per type; the name/type split exists so several
streams of one type can be added later (see [follow-ups](memory-workflow-followups.md)).

Job creation inserts a `load_inputs` stage at `stage_num` 0; the user's stages
start at 1. The request's top-level `inputs` map (stream name → typed source,
e.g. a memory group with its filters) is stored only in that stage's config
(`LoadInputsConfig`), not in the job config. The loader is the only action that
reads source data from PostgreSQL; `chapter` is always loaded.

Each stage config model has a `signature()` returning an `ActionSignature`:
required `inputs`, `optional_inputs`, `outputs`, and `drops` (all name → type).
The loader's outputs are computed from its `inputs`; the others are fixed class
constants. `stage_config(action, config)` parses a stored stage row into its
typed config. Streams a stage neither outputs nor drops pass through.

| Action | Inputs | Outputs |
| --- | --- | --- |
| `load_inputs` | none | `chapter` plus each declared stream |
| `prune_memories` | `chapter`, `memories` | `memories` |
| `translate` | `chapter`; `memories`, `terms`, `conventions` optional | `chapter` |

`trace_pipeline` in [types.py](../../backend/src/translations/types.py) is the
single statement of the type rules. Starting from nothing, it links each stage's
input ports to the stage that last wrote each stream (`linked`, `broken` for a
missing required stream, `incompatible` for a wrong type, `absent` for a missing
optional one). A stage fits when no port is broken or incompatible; a fitting
stage removes what it drops and becomes the producer of what it outputs, and a
stage that does not fit changes nothing. The first signature is the loader's by
convention only: any signature without inputs can start a pipeline.

Two layers read the trace. `infer_pipeline` raises on the first stage with a
warning and otherwise returns the state after each stage;
`TranslationJobCreate.validate_pipeline` calls it at creation, and `stage_types`
in [inputs.py](../../backend/src/translations/actions/common/inputs.py) calls it
over the stored stage rows at run time, returning the state before the stage,
its signature, and the state after. `check_pipeline` in
[metadata.py](../../backend/src/translations/metadata.py) backs
`POST /translation-jobs/check`: it converts the trace into ports, links, lane
ends, and addable actions for the pipeline builder
([response models](../../backend/src/translations/pipeline_schemas.py)). It only
warns, skips stages that do not fit so later ones still get feedback, and uses
each action's class-level `SIGNATURE`, the least demanding one. Its request,
`TranslationJobDraft`, is the creation request with stages allowed to be empty;
`TranslationJobCreateRequest` inherits from it. Stage numbers in errors and
`source` indices are stored numbers, so "stage 1" is the user's first stage.

**Every task's output file is the full state after its stage**, not only what
the stage produced. A stage reads exactly one file, the previous stage's
(`resolve_inputs`, validated against the state before the stage), and writes
`output_records`: records of untouched streams copied forward, then its own,
validated against the state after. `select_streams` is the one filter wrapper;
an action's `prepare` narrows to its declared inputs. The shared
`group_by_chapter(records, streams)` helper in `actions/common/inputs.py` groups
validated, prefiltered records into stream-name → record dictionaries, yielding
each chapter once all requested streams are present regardless of record order
or type. It raises for incomplete groups at exhaustion and relies on upstream
artifact validation for duplicate/type/chapter checks. Translation uses it to
wait for enabled context records; memory pruning uses it for its two required
inputs. Both handle record types locally. Absent optional streams require no
record and enabled empty streams are valid.

Records carry `chapter_id`, `stream`, a `data_name` type discriminator, and a
payload; the logical key is `(chapter_id, stream)`. `validate_output_records`
takes the expected name → type mapping and enforces exactly one record per
chapter per stream of the declared type. **Exhaust the iterator before
publishing**; completeness is checked at the end. `store_lines` in
[files.py](../../backend/src/translations/actions/common/files.py) is the only
spool-and-upload path, for both provider request files and output files, and
renews the lease while writing. The record key is embedded in provider request
IDs, so stream names will need a restricted character set once free naming is
allowed.

Adding a stream type needs a `StreamType` value, a record class, a loader source and
case in `iter_initial_records`, and a declaration on each action that reads it.
Group-level data (e.g. conventions) has no chapter; the current plan is to
repeat it on each chapter's record rather than add a batch-level record.
`TermsRecord` holds an exact source-form → translation map; `ConventionsRecord`
holds category/title/rule/rationale entries. `TermsInput` and `ConventionsInput`
each select a memory group independently. The loader snapshots pending/approved
term mappings (excluding rejected source terms), filtered by exact substring
matches in each pinned chapter, and pending/approved conventions of both
categories repeated for every chapter. Empty results still produce records.
The loader materializes the batch's pinned chapters once and reuses that list
for each stream, reading each group's mappings/conventions once.
Term retrieval lives in `actions/common/term_inputs.py`, alongside memory
retrieval in `memory_inputs.py`; the loader checks
each source group's novel ownership before reading it. Translation consumes
these streams in separate canonical-rendering and convention prompt sections;
both pass unchanged through pruning and translation artifacts. Tests verify
request content and preservation through repeated translation stages, not live
model adherence or translation quality.

Migration `a9d3e7c1b2f4` drops the per-batch snapshot column (the loader's output
replaced it) and renames the task's provider request file column to
`request_file_id`; it is not applied to a development database automatically.
The renamed column's foreign key keeps its old auto-generated name.

Leftovers as of 2026-11-14: action metadata supplies only `name`, `label`, and
`configSchema`; compatibility and availability come from the check endpoint.
The frontend create dialog has independent memory-group selectors for memories,
term translations, and conventions, sends those sources as top-level inputs,
and includes them in the check request. Its read-only lane diagram, including the labelled loader,
lives in [pipeline-diagram/](../../frontend/src/edit/panels/translations/pipeline-diagram/).
Layout and rendering use backend sources and link states without inferring types
or stream availability in the frontend.
Port types that differ from the lane header are labelled beside their dots;
all port types remain available in hover titles.

## Source and memory selection

Job creation pins each selected chapter's latest content ID in
`TranslationJobChapter`; later source edits do not silently replace that input.
Ranges have inclusive starts and exclusive ends. Stages and batches are stored
separately, with a task for each stage/batch pair. The loader captures chapters
and memories when its task first runs, not at creation; retrying the loader
re-reads the database.

[Memory retrieval](../../backend/src/translations/actions/common/memory_inputs.py)
runs only in the loader and uses active pending/approved memories at chapter N:
end is null or greater than N, and start is less than N by default
(`exclude_current_chapter`), otherwise less than or equal. This is not a
reconstruction of the state just before N. Optional filters distinguish `None`
(unfiltered) from `[]` (select none). These settings live on `MemoriesInput`.

[Pruning selections](../../backend/src/translations/actions/common/memory_selections.py)
are strict integer indices into the candidates in the previous stage's file,
which pruning re-reads in `finalize`. Duplicate or out-of-range indices and
unmatched selections/records fail; output retains original candidate order
rather than model-listed order. Structural validity does not establish that
pruning is semantically well tuned.

## Lifecycle and recovery

Each action module defines public step callbacks (`translate.prepare(context)`
etc.) and exports them as a `STEPS` tuple of `StepSpec`/`PollSpec` (task name,
expect/during/finish states, lease, poll interval). The module registers the
tuple on its `callbacks` with `register_steps`, so another `ActionCallbacks`
implementation can register the same specs. The Celery tasks are not bound to
module names: reach one by its registered name, e.g.
`app.tasks[TRANSLATE_PREPARE](task_id)` with names from `task_names.py`. Dispatch
stays in `CeleryActionCallbacks`; `run_claimed_step` (claim, run, finish or
fail; returns `unclaimed`/`advanced`/`pending`) and `ready_next_task` (mark the
next stage's task READY) take a session factory and contain no dispatch.

[async_actions.py](../../backend/src/translations/actions/async_actions.py)
(marked not audited, strictly for agent-eval use) implements `ActionCallbacks`
in-process. Awaiting `entrypoint(task_id)` runs that batch's remaining stages to
completion: steps run in `asyncio.to_thread` through `run_claimed_step` behind a
shared semaphore, pending polls `asyncio.sleep` their interval without holding
it, and `exitpoint` awaits the next stage's `entrypoint`. A step error is
recorded on the task and raised from `entrypoint`; an unclaimable task returns
without error. `build_async_registry(session_factory, max_concurrent_steps=...)`
registers every action's `STEPS`. To run a job, await each batch's stage-0
`load_inputs` entrypoint (e.g. with `asyncio.gather`). It bypasses
`control_translation_job`, and the actions still use the global object store
and registered batch clients. Tests do not cover poll waits: the claim gate
blocks reclaiming a poll before `next_poll_at`, so skipping the sleep stalls.

Model `qwen-flash-sync` uses
[sync_client.py](../../backend/src/translations/clients/sync_client.py) behind
the same `BatchJobClient` interface: `create_batch_job` sends each request
line's body to the chat-completions endpoint (model renamed to `qwen-flash`),
at most four at once with SDK retries for 429/5xx (one `asyncio.run` per batch,
`AsyncOpenAI` from a factory with `async_buffer`; the interface stays sync), and writes provider
batch-output lines to the object store at `translations/sync-batches/<uuid>.jsonl`.
That key is the job and output ID, and the first poll is complete, so a stage
needs no poll wait. A failed request becomes that chapter's failed line. The
whole batch runs inside `submit`, so it must finish within the 300 s submit lease;
use small batches. These objects have no `StoredFile` row and are never cleaned
up. The model appears in the editor's model list through `configSchema`.

Wrappers own commit/rollback, status, failure, and claim fields. Callbacks must
not commit, roll back, or close the session. Long work renews its lease
cooperatively; a blocking operation must fit inside that lease. An expired or
lost owner cannot publish completion. Queue messages carry task IDs, not the
worker's session/context.

Failure is represented by `failed_at`/`error` while retaining the lifecycle
status, so restart dispatch can choose the appropriate registered step. There
is no separate failed status in `TranslationTaskStatus`. Polling can release
and reschedule the same step. Controls commit state before publishing queue
work and report dispatch failures separately from successfully dispatched IDs.
Cancellation revokes claims and marks all unfinished scoped tasks, including
future stages, so an in-flight worker cannot continue the cancelled pipeline.

Use [control](../../backend/tests/translations/test_controls.py),
[claim](../../backend/tests/translations/test_claims.py),
[validation](../../backend/tests/translations/test_validation.py), and
[source deletion](../../backend/tests/translations/test_source_deletion.py)
tests when changing those boundaries. Action-specific coverage lives beside
them under [tests/translations](../../backend/tests/translations/).
