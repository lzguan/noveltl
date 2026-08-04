# Filter runners and persistence

**Last updated:** 2026-08-04

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

Workflow and grouping statuses use the same four values:

- `pending`;
- `processing`;
- `complete`;
- `failed`.

A runner first performs an atomic update matching the target ID, supplied job
ID, and `pending` status. If no row matches, it returns without doing work.
This prevents an old queued job from claiming a target after its job ID has
been replaced.

After a successful claim, an exception normally changes the still-owned
`processing` target to `failed` and stores the exception message. If ownership
or status changed during execution, the guarded status update does not
overwrite the newer state.

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

## Map

`PythonMapRunner` transforms every instance from one completed workflow into a
distinct output workflow.

Preconditions include:

- source and output workflow IDs must differ;
- the source must be complete;
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
provided a caller returns the grouping to a claimable state with the intended
job ID. The runner does not currently require the referenced workflow itself
to be complete.

## Batching and failure behavior

The default batch size is 1,000 for all four runners and can be overridden when
constructing a runner. Source, map, and filter use UUID keyset pagination.
Grouping repeatedly selects unassigned instances.

Map and filter verify that they examined the source count recorded before
processing. Group verifies that assignment count equals workflow instance
count. These checks detect some concurrent or incomplete execution, but the
subsystem does not yet define a general concurrency policy.

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
- an end-to-end label → filter → map → rename → group pipeline.

Runner tests require PostgreSQL because the persistence models use PostgreSQL
JSONB and integrate with the existing novel and label tables.

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
