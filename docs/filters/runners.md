# Filter runners and persistence

**Last updated:** 2026-08-12

Runners materialize or organize workflow instances using persisted schemas and
function definitions. They are synchronous backend classes with a shared
`execute(job_id, input)` protocol. They are invoked as Celery tasks in the
filters worker; see [workers and task queues](../project-structure.md#workers-and-task-queues).

## Persistence model

| Model | Purpose |
| --- | --- |
| `Workflow` | One materialized stage, its schema, job ownership, status, and message |
| `Instance` | One tagged record value belonging to a workflow |
| `FunctionDefinition` | A named serialized function AST |
| `Grouping` | One grouping calculation attached to a workflow and function |
| `GroupAssignment` | One instance's derived grouping key |

The models inherit repository-wide creation and update timestamps.

`Workflow` does not currently store a source workflow, operation definition,
novel scope, label-group scope, creator, or review history. Those relationships
are supplied transiently through runner input models or are not implemented.

## Job claim and statuses

Workflow and grouping statuses use the same five values:

- `new`;
- `pending`;
- `processing`;
- `complete`;
- `failed`.

Newly created resources begin in `new`. Services queue a filter job by
atomically moving every explicit member from `new`, `complete`, or—when
explicitly allowed—`failed` to `pending` under one job ID. Immediate neighbours
must be `complete` or `failed`; a `new` neighbour blocks queueing unless it is
included as a member. A workflow checks attached groupings, while a grouping
checks its parent workflow.

Map and filter jobs include both source and output workflows. Group jobs
include the workflow and grouping. Label-source jobs include the output
workflow. Annotation jobs include exactly the existing workflow being
augmented and no groupings.

A runner claims the same complete member set atomically. Every member must be
`pending` and owned by the supplied job ID or the runner returns without doing
work. This prevents partial claims and prevents an old queued job from running
after ownership has changed.

After execution, the complete persisted member set moves uniformly from
`processing` to either `complete` or `failed`, with one shared message. A
definite publication failure similarly moves the whole pending set to failed.
The job ID is retained as the last job owner. All transitions are guarded by
job ownership and current status, so stale deliveries make no changes.

## Label source

`PythonLabelSourceRunner` initializes a workflow from a label group.

It:

1. Requires the output schema to be exactly `{label: LabelRef}`.
2. Requires the output workflow to be empty.
3. Finds the novel containing the label group.
4. Finds the latest `ChapterContent` version for every chapter in that novel.
5. Selects labels from the requested group that belong to those latest
   versions.
6. Stores one label-reference instance per label in UUID-keyset batches.

The source runner reads all matching labels; it does not apply user permission
filters or a chapter-number range. An empty source completes successfully.

## Annotation

`PythonAnnotationRunner` adds requested mutable scalar fields to an existing
workflow schema and writes each requested default value into every instance.
It requires a job containing exactly the input workflow and no groupings. The
schema and instance updates commit together with successful job completion;
validation or update failures move the claimed workflow to failed.

## Map

`PythonMapRunner` transforms every instance from one completed workflow into a
distinct output workflow.

Preconditions include:

- source and output workflow IDs must differ;
- the source and output must have been queued and claimed together;
- the output must be empty;
- the function must accept exactly one record argument;
- the source schema must structurally satisfy that argument;
- the function must return a record;
- the output workflow schema must exactly equal the function output schema.

The runner parses each source value, preloads external dependencies, compiles
the function, and inserts one output instance for every source instance.
Transactions commit per batch.

## Filter

`PythonFilterRunner` evaluates a boolean function over each source instance and
copies passing values into a distinct output workflow.

It shares map's source, target, and input compatibility rules, with two
additional requirements:

- the output schema must equal the source schema;
- the function output must be boolean.

Filtering does not mutate or mark source instances. Excluded instances simply
do not appear in the derived workflow; the source stage remains intact.

## Group

`PythonGroupRunner` attaches a `Grouping` to one workflow and derives one key
for every instance.

The grouping function:

- must accept exactly one record argument;
- may require only fields compatible with the workflow schema;
- cannot depend on mutable workflow fields;
- must return an immutable string, integer, or boolean.

Assignments are stored separately from instance payloads and are unique per
grouping and instance. Multiple instances may share the same raw key. There is
no separate persisted group row, count, sample, or review decision yet.

Unlike the output-producing runners, grouping queries only instances missing
an assignment. It can therefore resume after already committed batches,
provided a caller queues the workflow and grouping together under the intended
job ID.

## Batching and failure behavior

The default batch size is 1,000 for the four batched runners and can be overridden when
constructing a runner. Source, map, and filter use UUID keyset pagination.
Grouping repeatedly selects unassigned instances.

Map and filter verify that they examined the source count recorded before
processing. Group verifies that assignment count equals workflow instance
count. Queue and claim reservations prevent jobs that touch the same workflow
or workflow/grouping neighbourhood from executing concurrently.

Each batch commits independently. A terminal failure may therefore leave
instances or assignments already persisted:

- grouping is designed to skip existing assignments;
- source, map, and filter require an empty output when starting and do not
  provide a general failed-job resume path;
- there is no per-instance failure record;
- there is no progress column beyond status and message.

Job ownership makes duplicate or stale delivery safe to ignore, but it is not
equivalent to full retryability.

## Current integration boundary

Backend integration is complete:

- [`alembic/versions/d386545e4f4a_filters.py`](../../backend/alembic/versions/d386545e4f4a_filters.py)
  creates the tables;
- [`filters/router.py`](../../backend/src/filters/router.py) exposes workflows
  and operations, and is registered in
  [`main.py`](../../backend/src/main.py);
- [`filters/service.py`](../../backend/src/filters/service.py) creates and
  connects pipeline stages;
- [`filters/dispatch/celery.py`](../../backend/src/filters/dispatch/celery.py)
  enqueues runner jobs, which
  [`filters/worker/tasks.py`](../../backend/src/filters/worker/tasks.py)
  executes in the filters worker;
- [`filters/permissions.py`](../../backend/src/filters/permissions.py) scopes
  execution to users.

One piece is still missing:

- no frontend renders workflows, instances, or groups.

Until it exists, the runners are reachable through the HTTP API but have no
user-facing entry point, so tests and direct backend callers remain the
primary consumers.

## Testing

The filter test suite covers:

- strict type parsing and structural compatibility;
- function validation and composition;
- dependency resolution and compilation;
- label-source selection from latest content versions;
- map, filter, and group preconditions;
- bounded batches, stale job IDs, partial commits, and grouping resumption;
- an end-to-end label → filter → map → rename → group pipeline;
- Redis-backed Celery dispatch of a user workflow through label-source,
  annotation, filter, map, and group workers, including persisted outputs.

Runner tests require PostgreSQL because the persistence models use PostgreSQL
JSONB and integrate with the existing novel and label tables.
The Celery integration test additionally requires the configured `test_redis`
service and is marked `integration` and `slow`, so it must be selected
explicitly with `pytest -m integration`.

## Code guide

- [`models.py`](../../backend/src/filters/models.py): persistence schema
- [`runners/interfaces/runner.py`](../../backend/src/filters/runners/interfaces/runner.py):
  runner protocol
- [`runners/python/`](../../backend/src/filters/runners/python/): runner
  implementations
- [`test_python_runner_pipeline.py`](../../backend/tests/filters/test_python_runner_pipeline.py):
  complete pipeline example
- [Future workflow product](design/workflows.md): review and application
  capabilities planned above this foundation
