# Memory-job implementation

## Source map

| Responsibility | Source |
| --- | --- |
| Stored parameter versions and internal stage configs | [config.py](../../backend/src/memory/agent/config.py) |
| Job/task rows | [models.py](../../backend/src/memory/models.py) |
| Inactive typed workspace/shadow schema | [shadow_models.py](../../backend/src/memory/shadow_models.py) |
| Workspace-aware read composition | [overlay.py](../../backend/src/memory/overlay.py) |
| Typed shadow upserts and workspace validation | [staging.py](../../backend/src/memory/staging.py) |
| Creation, claims, task status transitions | [tasks/jobs.py](../../backend/src/memory/agent/tasks/jobs.py) |
| Execution and transaction boundaries | [tasks/tasks.py](../../backend/src/memory/agent/tasks/tasks.py) |
| Continuity summary reads and writes | [memory/access.py](../../backend/src/memory/access.py) |
| Glossary queries, including event history and supersede checks | [glossary/access.py](../../backend/src/memory/plugins/glossary/access.py) |
| Agent construction and output validation | [agents/](../../backend/src/memory/agent/agents/) (one factory module per agent; recording owns the user-selectable toolset registry), [registry.py](../../backend/src/memory/agent/registry.py) (shared model configuration) |
| Thin stage runners | [stages/](../../backend/src/memory/agent/stages/) |
| Access checks, dispatch, response construction | [service.py](../../backend/src/memory/agent/service.py) |
| Worker entry points and result logging | [dispatch/](../../backend/src/memory/agent/dispatch/) |

## Configuration and task identity

`MemoryJob.job_params` stores versioned JSON exactly as written: the create
endpoint and `make_job` accept V1 (recording only), V2 (one optional field per
stage type), or V3 (an ordered `stages` list of `StageConfig` models tagged by
`stage_name`). `resolve_stages` turns any version into the ordered stage list,
with one `match` branch per version; a task's `stage_num` indexes it. V2 resolves
as recording → conventions → naming. `upgrade_job_params` wraps that list in V3,
and `parse_job_params` validates stored JSON and upgrades it, so API responses
always return V3. V1/V2 are to be deleted when migrations are squashed before
deploy, not by a data migration.

Creation enumerates the selected configs and inserts every stage's tasks in one
`INSERT .. FROM SELECT` over a `UNION ALL`. `stage_task_chapters` in
[jobs.py](../../backend/src/memory/agent/tasks/jobs.py) picks each stage's
chapters: one task per chapter, except the conventions stage, which gets one
task on the range's last chapter so barriers place it after all recording and
before any naming. Chapter ranges have an inclusive start and exclusive end. A naming-only job has naming at stage 0. The task primary key is
`(memory_job_id, chapter_id, stage_num)`. Tasks store neither a stage name nor
a config. API responses expose `stage_num`, and the frontend names a task's
stage with `jobParams.stages[stageNum].stageName` from the V3 response; it does
not reproduce backend stage order.

Execution builds `dict[int, StageConfig]` from the V3 stage list.
`_run_single_task` uses the task's stage number to retrieve its config, then
dispatches on the config type. Keep this mapping consistent with creation.
A name-keyed map would collapse configs if a future job format permits multiple
stages of the same type. Stage numbers are not fixed IDs for recording or naming.

## Running and retrying

`run_all_tasks` delegates to `run_tasks`, which acquires the job claim and uses
`claim_next_task`. Stages are job-wide barriers: tasks run ordered by stage
number, then chapter number, so every chapter is recorded before any naming
starts. The next task is claimed only if pending, so a failed task blocks later
work until retried. One task executes at a time per claimed job.

Ordering lives in a `TaskSchedule` ([schedule.py](../../backend/src/memory/agent/tasks/schedule.py))
resolved from job params by `get_schedule`. It returns composable queries,
so claims stay single atomic statements: `next_unfinished` (used by
`claim_next_task` and `service.start_job`'s blocking-failure check) and
`unfinished_prerequisites` (used by `claim_task` and `service.start_task`).
`run_order` gives the ORDER BY terms for execution order; `next_unfinished` and
`service.query_tasks` both use it, so the task list shows tasks in the order
they run.
`run_tasks` resolves the schedule beside the stages and passes it to the claim
function. Invariant: the next task never has unfinished prerequisites. All
current params use `StageBarrierSchedule`; configurable orders (e.g. windows of
N chapters for conventions) are planned as a later params option; see
[follow-ups](memory-workflow-followups.md).

`run_one_task` uses the same orchestration with a specific task selector. Direct
execution waits for lower stages across the job, but does not enforce chapter
order within a stage.

`arun_tasks` owns the session for a task's writes. `release_task` commits writes
and completion together, conditional on continued claim ownership. Failure rolls
back that task's writes before recording failure in a separate session. Naming
failure therefore preserves successful recording. Expired claims can be replaced;
the old worker cannot finalize work after losing ownership.

The retry service resets and enqueues the selected failed task. It does not
automatically run the rest of the job; starting the job continues pending work.
An abort marks processing tasks failed and invalidates the claim; it is not
evidence of an inference failure by itself. Celery has no result backend;
completed model results and skipped naming stages are logged by the worker.

Each stage loads the latest chapter content. No agent run context or source
revision is persisted between memory stages. Agent creation happens per stage;
[term naming](term-translations.md) skips it when there is nothing to translate.

Agent toolsets and capabilities delegate entity SQL to access functions. The
continuity capability handles prompt injection and passes its output to
`write_continuity_summary`; `read_previous_continuity_summary` owns predecessor
and source-version eligibility. Transformation tools keep occurrence-retention
decisions and model-facing errors while glossary access owns their history query
and exact-subject supersede check. Access functions do not commit; the existing
task transaction still owns publication.

## Shadow storage schema (not connected to execution)

[Migration f8b2c4d6e901](../../backend/alembic/versions/f8b2c4d6e901_add_memory_shadow_tables.py)
adds execution workspaces referencing `(job, chapter, stage)` and typed shadows
for memories, terms, associations, translations, and conventions. Each execution
creates a fresh workspace; multiple workspaces can reference the same task.
Claim tokens remain with the worker and job, and attempt counts remain on tasks.
Task/workspace deletion cascades to its drafts. No worker or API currently uses
these tables; the transaction and completion behavior described above is unchanged.

Published and shadow entities inherit column-only mixins defined beside each
published model in its owning `models.py`. Keys, foreign keys, checks, and indexes
belong to the concrete tables. Shadows use `(workspace_id, entity key)` primary
keys. `deleted` denotes a tombstone. A create-then-delete can remove its draft
rather than create a tombstone. Active term names and continuity summaries
retain workspace-local uniqueness; tombstones do not block replacements.

These model modules import `Base` from `src.model_base`, which declares only the
shared ORM base and timestamps. `src.models` re-exports the same class and remains
the complete model registry used for metadata creation/migrations. Keeping the
base separate avoids registering shadow models while an imported published
model is still defining its column mixins; model/access imports can start before
the global registry without an import cycle.

Entity IDs, association endpoints, translation term IDs, and supersedes IDs
deliberately do not reference published rows with foreign keys: new parents may
exist only as drafts. Existing group/content references still have foreign keys.
The agreed publication policy is to merge when the worker still owns an unexpired
job claim and the resulting data satisfies existing validity and editability
rules; there is no original-timestamp conflict check. Publication reference validation,
claim checks, cleanup, and atomic publication are subsequent work; the schema itself
does not enforce them. [Schema tests](../../backend/tests/memory/test_shadow_schema.py)
exercise the migration in an isolated PostgreSQL schema, including parity with
ORM metadata, unpublished IDs, workspace isolation, constraints, and cleanup.

## Workspace reads (not enabled in jobs)

`MemAccessContext.workspace_id` defaults to `None`. With no workspace, accessors
query the published models directly. With a workspace, `visible_rows` builds a
per-entity `UNION ALL` between published rows lacking any matching shadow key
and nondeleted shadow rows belonging to that workspace. The exclusion considers
all shadow rows before caller filters, so a rejected, renamed, recategorized,
ended, or deleted draft cannot expose its old published version. Association
overrides match both entity IDs. Filters, counts, ordering, and pagination use
the combined view; joins use overlays for every staged entity involved.

Glossary chapter/range reads, inspection, alias traversal, event history/checks,
term searches/missing-term diagnostics, translations, conventions, and continuity
reads support the overlay. Group-only read accessors take a keyword-only
`workspace_id`; naming and conventions context builders pass it through.
Source chapter text and access-context group/chapter validation remain published.

`workspace_read` sets an ORM identity token per workspace and refreshes existing
query results. This prevents cached published objects, another workspace, or a
previous draft read from supplying stale payloads. These ORM results are read
snapshots: consume/materialize them before session commit/expiry and do not edit
them through the published ORM mapper. Short transaction boundaries and plain
tool results remain part of the later worker/write integration.

No execution path creates workspaces yet. Guarded atomic publication and worker
integration remain subsequent work. [Read tests](../../backend/tests/memory/test_shadow_reads.py)
seed drafts directly and exercise the real accessors and context builders against
PostgreSQL, including cache isolation, masks before filtering, pagination,
composite association keys, aliases, translations, conventions, and continuity.

A one-time synthetic PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` check used 1,000 terms,
20,000 memories, 20,200 associations, and 70 shadow rows in temporary test tables.
Summed warm execution across a lookup's three SELECTs was about 0.9 ms published
and 50 ms with overlays; alias-aware workspace retrieval used five SELECTs and
about 76 ms. These local measurements exclude client/ORM overhead and do not
establish production-scale performance; the overlay adds material query cost.

## Workspace writes (not enabled in jobs)

Agent mutations select the visible row before changing it and write only to the
typed shadow table when a workspace is supplied. `stage_record` upserts by the
workspace/entity key, preserving an existing row's payload, UUID, and creation
timestamp while applying explicit changes. It never mutates an overlay snapshot
through the published ORM mapper. Accessors do not commit or own the outer
transaction; caller savepoints still roll back a failed tool/output attempt.

Workspace-aware paths cover term creation, memory creation/supersession/expiry,
association creation, term translations, convention CRUD, and continuity writes.
Term creation checks published-plus-shadow name uniqueness; associations resolve
exact terms through the overlay, including unpublished terms. Naming preserves
usable translations; continuity preserves reviewed/user-authored summaries;
convention updates/deletes retain their creator and pending-status conditions.
Convention deletion removes a draft with no published counterpart, otherwise it
writes a tombstone. No extra agent deletion APIs were introduced.

`check_workspace` validates the workspace's job/group and, for `MemAccessContext`,
its task chapter. Invalid/missing workspaces raise `MemoryWorkspaceNotFoundException`.
Claim ownership is deliberately not checked by staging: the worker's claim will
guard atomic publication in the later integration step. Human review accessors
(`approve_*`, `reject_*`, `mark_*_pending` for memories/terms) remain published-only
and are not exposed to agents. Source-text queries also use published chapter data.
Calls without a workspace preserve the existing published-table write path.

[Write tests](../../backend/tests/memory/test_shadow_writes.py) exercise the real
accessors and agent tool/output adapters against PostgreSQL: committed drafts stay
unpublished, other workspaces remain isolated, supersession/expiry affect only
drafts, protected choices survive, create/delete and tombstone behavior differ,
and failed savepoints roll back all staged output. Read/write tests share the
synthetic workspace fixture in `tests/fixtures/memory_workspaces.py`.

## Adding a stage or agent

Checklist, derived from adding the conventions stage. Paths are under
`backend/src/memory/agent/` unless noted.

Backend:

- [config.py](../../backend/src/memory/agent/config.py): a `<X>Config`
  (`extra="forbid"`) and a `<X>StageConfig` with a `stage_name` literal, added
  to the `StageConfig` union. V3 lists stages in order, so nothing else in the
  params changes; do not extend the stored-only V1/V2 models.
- `StageName` in [memory/types.py](../../backend/src/memory/types.py).
- A `stage_task_chapters` case in `tasks/jobs.py`. It is a `match`, so
  pyrefly reports a missing case.
- `agents/<x>.py`: factory using `registry.model_configuration`, plus its output
  type. Prompts go in `prompts/<x>.py`; a thin runner goes in `stages/<x>.py`.
- In `tasks/tasks.py`: a `_run_single_task` branch and the
  `CompletedMemoryTask.result` union. The Celery result payload already dumps
  any `BaseModel` output.

API and frontend:

- Regenerate OpenAPI and the client ([verification](verification.md)); the new
  `StageConfig` member is a public schema change.
- [stages.ts](../../frontend/src/memory/agent/stages.ts): entries in
  `MEMORY_STAGE_LABELS` and `MEMORY_STAGE_TASK_NOUNS`. `MemoryStageName` comes
  from the generated `StageConfig`, so a missing label fails the type check.
- [CreateMemoryJobForm.tsx](../../frontend/src/memory/agent/components/CreateMemoryJobForm.tsx):
  a stage section (checkbox, then its settings indented under it), the form
  values, the at-least-one-stage check, and a `stages` entry in run order in the submitted V3 params.

Tests: stage order and discriminator cases in `test_memory_job_config.py`,
task materialization in `test_memory_agent_tasks.py`, and the submitted
stages in `CreateMemoryJobForm.test.tsx`.
When stubbing inference, monkeypatch `model_configuration` on the `agents/<x>`
module that imported it, not on `registry`.

## Tests

- [Config](../../backend/tests/memory/test_memory_job_config.py): version adapters and stage selection.
- [Tasks](../../backend/tests/memory/test_memory_agent_tasks.py): transactions, claim loss, naming failure/retry, and no-work naming.
- [Service](../../backend/tests/memory/test_memory_agent_service.py): permissions, task identity, and dispatch.
- [Router](../../backend/tests/memory/test_memory_agent_router.py): public task controls and stage numbers.
- [Migration](../../backend/tests/memory/test_memory_stage_migration.py): legacy jobs and upgrade/downgrade round trip in an isolated PostgreSQL schema.
