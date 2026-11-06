# Memory-job implementation

## Source map

| Responsibility | Source |
| --- | --- |
| Stored parameter versions and internal stage configs | [config.py](../../backend/src/memory/agent/config.py) |
| Job/task rows | [models.py](../../backend/src/memory/models.py) |
| Creation, claims, task status transitions | [tasks/jobs.py](../../backend/src/memory/agent/tasks/jobs.py) |
| Execution and transaction boundaries | [tasks/tasks.py](../../backend/src/memory/agent/tasks/tasks.py) |
| Agent construction and output validation | [agents/](../../backend/src/memory/agent/agents/) (one factory module per agent; recording owns the user-selectable toolset registry), [registry.py](../../backend/src/memory/agent/registry.py) (shared model configuration) |
| Thin stage runners | [stages/](../../backend/src/memory/agent/stages/) |
| Access checks, dispatch, response construction | [service.py](../../backend/src/memory/agent/service.py) |
| Worker entry points and result logging | [dispatch/](../../backend/src/memory/agent/dispatch/) |

## Configuration and task identity

`MemoryJob.job_params` stores versioned JSON. V1 retains the original recording
fields (`model_name`, `toolsets`). V2 selects any of recording, conventions summarization, and term translation
(resolved in that order).
`resolve_stages` adapts either version into ordered, discriminated `StageConfig`
models. External parameter models do not contain `stage_name`.

Creation enumerates the selected configs and inserts every stage's tasks in one
`INSERT .. FROM SELECT` over a `UNION ALL`. `stage_task_chapters` in
[jobs.py](../../backend/src/memory/agent/tasks/jobs.py) picks each stage's
chapters: one task per chapter, except the conventions stage, which gets one
task on the range's last chapter so barriers place it after all recording and
before any naming. Chapter ranges have an inclusive start and exclusive end. A naming-only job has naming at stage 0. The task primary key is
`(memory_job_id, chapter_id, stage_num)`. Tasks store neither a stage name nor
a config. API responses expose `stage_num`; frontend helpers derive the name
from job params in [stages.ts](../../frontend/src/memory/agent/stages.ts).

Execution builds `dict[int, StageConfig]` from the same resolution order.
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
`run_tasks` resolves the schedule beside the stages and passes it to the claim
function. Invariant: the next task never has unfinished prerequisites. All
current params use `StageBarrierSchedule`; configurable orders (e.g. windows of
N chapters for conventions) are planned for job params V3; see
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

## Adding a stage or agent

Checklist, derived from adding the conventions stage. Paths are under
`backend/src/memory/agent/` unless noted.

Backend:

- [config.py](../../backend/src/memory/agent/config.py): an external `<X>Config`
  (`extra="forbid"`, no `stage_name`) and a `<X>StageConfig` with a
  `stage_name` literal; add it to the `StageConfig` union, a `JobParamsV2`
  field, a `None` property on `JobParamsV1`, `require_stage`, and
  `resolve_stages` in its execution position.
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
  `JobParamsV2` field is a public schema change.
- [stages.ts](../../frontend/src/memory/agent/stages.ts): the stage name,
  `MEMORY_STAGE_LABELS`, `MEMORY_STAGE_TASK_NOUNS`, and the same order as
  `resolve_stages`. A mismatch silently mislabels tasks, because tasks only
  store `stage_num`.
- [CreateMemoryJobForm.tsx](../../frontend/src/memory/agent/components/CreateMemoryJobForm.tsx)
  once the stage works; until then, the API accepts a stage that fails at run time.

Tests: stage order and discriminator cases in `test_memory_job_config.py`,
task materialization in `test_memory_agent_tasks.py`, and `stages.test.ts`.
When stubbing inference, monkeypatch `model_configuration` on the `agents/<x>`
module that imported it, not on `registry`.

## Tests

- [Config](../../backend/tests/memory/test_memory_job_config.py): version adapters and stage selection.
- [Tasks](../../backend/tests/memory/test_memory_agent_tasks.py): transactions, claim loss, naming failure/retry, and no-work naming.
- [Service](../../backend/tests/memory/test_memory_agent_service.py): permissions, task identity, and dispatch.
- [Router](../../backend/tests/memory/test_memory_agent_router.py): public task controls and stage numbers.
- [Migration](../../backend/tests/memory/test_memory_stage_migration.py): legacy jobs and upgrade/downgrade round trip in an isolated PostgreSQL schema.
