# Chapter-translation pipeline

Code checked 2026-11-03. This is the batch chapter-translation subsystem, distinct
from the memory recording and glossary [term-naming jobs](memory-jobs.md).
Canonical term mappings are not yet wired into these actions.

## Entry points

| Responsibility | Source |
| --- | --- |
| Logical action signatures and lifecycle states | [types.py](../../backend/src/translations/types.py) |
| Public envelope, typed internal configs, pipeline compatibility | [schemas.py](../../backend/src/translations/schemas.py) |
| Action discovery and form metadata | [metadata.py](../../backend/src/translations/metadata.py) |
| Job/stage/batch/task persistence and pinned chapters | [models.py](../../backend/src/translations/models.py), [tasks/jobs.py](../../backend/src/translations/tasks/jobs.py) |
| Controls and dispatch reporting | [service.py](../../backend/src/translations/service.py) |
| Worker callback contract and wrappers | [actions.py](../../backend/src/translations/actions/actions.py), [celery_actions.py](../../backend/src/translations/actions/celery_actions.py) |
| Lease ownership | [claims.py](../../backend/src/translations/tasks/claims.py) |
| Normalized data, JSONL, output completeness | [records.py](../../backend/src/translations/records.py), [jsonl.py](../../backend/src/translations/jsonl.py), [validation.py](../../backend/src/translations/validation.py) |
| Provider transport and response codecs | [clients/](../../backend/src/translations/clients/), [codecs/](../../backend/src/translations/codecs/) |
| Frontend pipeline builder and results viewer | [translations panel](../../frontend/src/edit/panels/translations/) |

## Actions produce explicit artifacts

An action signature describes the complete logical components of its output
artifact, not the Python callback return type. Mutation callbacks take
`ActionTaskContext` and return `None`; poll callbacks return whether to advance.
The callbacks write artifacts/task fields inside the wrapper-owned transaction.

| Action | Input components | Output components |
| --- | --- | --- |
| `prune_memories` | chapter, memories | memories |
| `combine_chapter` | memories | chapter, memories |
| `translate_with_memories` | chapter, memories | chapter |
| `translate` | chapter | chapter |

The internal request validates adjacent signature compatibility. Pruning does
not implicitly pass the chapter through: `combine_chapter` restores the pinned
source chapter alongside the selected memories. It is not allowed first.
Adding an action requires considering signatures, typed config validation,
metadata, registration, and normalized record support together.

Records have a `data_name` discriminator and a logical key of
`(chapter_id, data_name)` within the task artifact. Provider chunk/request IDs
are separate. `validate_output_records` enforces exactly the required component
set for the batch: no missing/duplicate components, foreign chapters, or extra
types. **Exhaust the iterator before publishing**; completeness is checked at
the end, including when a streamed upload appears to have succeeded so far.

## Source and memory selection

Job creation pins each selected chapter's latest content ID in
`TranslationJobChapter`; later source edits do not silently replace that input.
Ranges have inclusive starts and exclusive ends. Stages and batches are stored
separately, with a task for each stage/batch pair.

[Memory retrieval](../../backend/src/translations/actions/common/memory_inputs.py)
uses active pending/approved memories at chapter N: end is null or greater than
N, and start is less than N by default (`exclude_current_chapter`), otherwise
less than or equal. This is not a reconstruction of the state just before N.
Optional filters distinguish `None` (unfiltered) from `[]` (select none).

[Pruning selections](../../backend/src/translations/actions/common/memory_selections.py)
are strict integer indices into persisted candidates. Duplicate or out-of-range
indices and unmatched selections/records fail; output retains original candidate
order rather than model-listed order. Structural validity does not establish
that pruning is semantically well tuned.

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
