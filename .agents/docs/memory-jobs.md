# Memory-job implementation

## Source map

| Responsibility | Source |
| --- | --- |
| Stored parameter versions and internal stage configs | [config.py](../../backend/src/memory/agent/config.py) |
| Job/task rows | [models.py](../../backend/src/memory/models.py) |
| Creation, claims, task status transitions | [tasks/jobs.py](../../backend/src/memory/agent/tasks/jobs.py) |
| Execution and transaction boundaries | [tasks/tasks.py](../../backend/src/memory/agent/tasks/tasks.py) |
| Agent construction and output validation | [agent.py](../../backend/src/memory/agent/agent.py) |
| Thin stage runners | [stages/](../../backend/src/memory/agent/stages/) |
| Access checks, dispatch, response construction | [service.py](../../backend/src/memory/agent/service.py) |
| Worker entry points and result logging | [dispatch/](../../backend/src/memory/agent/dispatch/) |

## Configuration and task identity

`MemoryJob.job_params` stores versioned JSON. V1 retains the original recording
fields (`model_name`, `toolsets`). V2 selects recording and/or term translation.
`resolve_stages` adapts either version into ordered, discriminated `StageConfig`
models. External parameter models do not contain `stage_name`.

Creation enumerates the selected configs and inserts one task per chapter and
stage. Chapter ranges have an inclusive start and exclusive end. A naming-only job has naming at stage 0. The task primary key is
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
`claim_next_task`. The query selects the first unfinished task ordered by chapter
number, then stage number. It claims that task only if pending, so a failed task
blocks later work until retried. One task executes at a time per claimed job.

`run_one_task` uses the same orchestration with a specific task selector. Direct
execution checks for unfinished preceding stages in that chapter; it does not
enforce completion of all previous chapters.

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

## Tests

- [Config](../../backend/tests/memory/test_memory_job_config.py): version adapters and stage selection.
- [Tasks](../../backend/tests/memory/test_memory_agent_tasks.py): transactions, claim loss, naming failure/retry, and no-work naming.
- [Service](../../backend/tests/memory/test_memory_agent_service.py): permissions, task identity, and dispatch.
- [Router](../../backend/tests/memory/test_memory_agent_router.py): public task controls and stage numbers.
- [Migration](../../backend/tests/memory/test_memory_stage_migration.py): legacy jobs and upgrade/downgrade round trip in an isolated PostgreSQL schema.
