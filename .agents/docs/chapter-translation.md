# Chapter-translation pipeline

Code checked 2026-11-14. This is the batch chapter-translation subsystem, distinct
from the memory recording and glossary [term-naming jobs](memory-jobs.md).
Term translations and conventions are not yet wired into these actions; the
stream design below is the intended route for them.

## Entry points

| Responsibility | Source |
| --- | --- |
| Signature type, type inference, lifecycle states | [types.py](../../backend/src/translations/types.py) |
| Public envelope, typed stage configs and their signatures, input sources | [schemas.py](../../backend/src/translations/schemas.py) |
| Reading the previous stage, building a stage's output, storing files | [actions/common/](../../backend/src/translations/actions/common/) |
| Action discovery and form metadata | [metadata.py](../../backend/src/translations/metadata.py) |
| Job/stage/batch/task persistence and pinned chapters | [models.py](../../backend/src/translations/models.py), [tasks/jobs.py](../../backend/src/translations/tasks/jobs.py) |
| Controls and dispatch reporting | [service.py](../../backend/src/translations/service.py) |
| Worker callback contract and wrappers | [actions.py](../../backend/src/translations/actions/actions.py), [celery_actions.py](../../backend/src/translations/actions/celery_actions.py) |
| Lease ownership | [claims.py](../../backend/src/translations/tasks/claims.py) |
| Normalized data, JSONL, output completeness | [records.py](../../backend/src/translations/records.py), [jsonl.py](../../backend/src/translations/jsonl.py), [validation.py](../../backend/src/translations/validation.py) |
| Provider transport and response codecs | [clients/](../../backend/src/translations/clients/), [codecs/](../../backend/src/translations/codecs/) |
| Frontend pipeline builder and results viewer | [translations panel](../../frontend/src/edit/panels/translations/) |

## Streams, signatures, and full-state artifacts

A job's data flows as named **streams**, each with a type (`DataName`: `chapter`,
`memories`). For now a stream must be named after its type, so there is one
stream per type; the name/type split exists so several streams of one type can
be added later (see [follow-ups](memory-workflow-followups.md)).

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
| `translate` | `chapter`; `memories` optional | `chapter` |

`infer_type` / `infer_pipeline` in [types.py](../../backend/src/translations/types.py)
are the single checker. `TranslationJobCreate.validate_pipeline` folds them over
the loader and the stages at creation; `stage_types` in
[inputs.py](../../backend/src/translations/actions/common/inputs.py) folds them
over the stored stage rows at run time and returns the state before the stage,
its signature, and the state after. Stage numbers in errors are stored numbers,
so "stage 1" is the user's first stage.

**Every task's output file is the full state after its stage**, not only what
the stage produced. A stage reads exactly one file, the previous stage's
(`resolve_inputs`, validated against the state before the stage), and writes
`output_records`: records of untouched streams copied forward, then its own,
validated against the state after. `select_streams` is the one filter wrapper;
an action's `prepare` narrows to its declared inputs. Pairing a chapter with its
memories is done inside each action, not in common code, and currently
distinguishes records by type rather than stream name.

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

Adding a stream type needs a `DataName`, a record class, a loader source and
case in `iter_initial_records`, and a declaration on each action that reads it.
Group-level data (e.g. conventions) has no chapter; the current plan is to
repeat it on each chapter's record rather than add a batch-level record.

Leftovers as of 2026-11-14: `translation_batches.initial_file_id` and
`publish_initial_file` are unused (the loader's output replaced the batch
snapshot) and await a migration, which should also rename the task's
`input_file_id` (the provider request file, not pipeline input). The metadata
endpoint's `inputTypes` / `outputTypes` ignore optional inputs. The frontend
create dialog still sends the old request shape and has no label for the
`load_inputs` stage; a dry-run validate endpoint is planned to replace its own
compatibility logic.

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
