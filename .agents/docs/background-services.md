# Background services and stored files

Code checked 2026-11-03. Use the service's own worker and progress model when
debugging; the request-result cache is a different subsystem.

## Worker map

| Work | Queue | Broker database setting (default) | Registration |
| --- | --- | --- | --- |
| Autolabel inference | Celery [autolabels](../../backend/src/autolabels/inference/celery_app.py) | `AUTOLABELS_DATABASE` (1) | [dispatch/celery.py](../../backend/src/autolabels/inference/dispatch/celery.py) |
| Filter runners | Celery [filters](../../backend/src/filters/celery_app.py) | `FILTERS_DATABASE` (0) | [dispatch/celery.py](../../backend/src/filters/dispatch/celery.py) |
| Memory recording/naming | taskiq [memory-agent broker](../../backend/src/memory/agent/broker.py) | `AGENT_DATABASE` (3) | [dispatch/taskiq_worker.py](../../backend/src/memory/agent/dispatch/taskiq_worker.py) |
| Label promotion | taskiq [jobs broker](../../backend/src/jobs/broker.py) | `JOBS_DATABASE` (5) | [promotions/tasks.py](../../backend/src/autolabels/promotions/tasks.py) |
| Chapter translation | Celery [translations](../../backend/src/translations/celery_app.py) | `TRANSLATIONS_DATABASE` (4) | [actions package](../../backend/src/translations/actions/__init__.py) |

Both taskiq brokers come from `make_jobs_broker` (Redis streams, consumer group
starting at `0-0` so work enqueued before the first worker start is delivered).
The memory agent keeps a selectable Celery implementation
([celery_app.py](../../backend/src/memory/agent/celery_app.py),
[dispatch/celery_worker.py](../../backend/src/memory/agent/dispatch/celery_worker.py));
`get_dispatcher` in [dispatch/dependencies.py](../../backend/src/memory/agent/dispatch/dependencies.py)
and the Dockerfile `memory-agent-worker` CMD choose which one runs.

Defaults come from [config.py](../../backend/src/config.py); inspect actual
deployment settings when diagnosing a connection. Request-result caching uses
`REQUESTS_DATABASE` (2) via [redis_conn.py](../../backend/src/requests/redis_conn.py).
These apps do not configure a Celery result backend. Do not assume a
`celery-task-meta-*` key exists or use queue delivery as evidence of completion.
Use service persistence and worker logs for progress and failure analysis.

Autolabels, filters, and translations currently configure Celery prefork workers
with concurrency 2, each in its own `celeryconfig.py`. The memory agent runs one
taskiq process with `--max-async-tasks 64` on a single event loop; this relies on
the memory module being fully async (no sync database calls on the loop; see
[memory-jobs.md](memory-jobs.md)). Worker concurrency is not concurrency inside a
single memory job, which is [claimed sequentially](memory-jobs.md).

Celery dispatchers use named `send_task` calls; taskiq dispatchers kick tasks by
name with `AsyncKicker`. Either way, worker registration modules import the
implementation and API-side dispatch must not, so the API does not pull in
inference/runner/agent SDKs. Chapter translation instead registers action callbacks;
its [wrapper contract](chapter-translation.md) owns lifecycle transitions.

Worker services are behind the `manual` profile in [compose.yaml](../../compose.yaml).
Use [compose.local.yaml](../../compose.local.yaml) when choosing local build
targets instead of published images. The memory result sink is configured by
`MEMORY_AGENT_LOG_DIR` and `MEMORY_AGENT_LOG_FILENAME`; successful/skipped result
JSONL entries alone cannot explain every failed task.

The older worker inventory in `docs/project-structure.md` describes autolabels
and filters only. It is not an exhaustive current worker map. It was left
unchanged under the human-documentation editing rule.

## Object storage and transaction ownership

The [files service](../../backend/src/files/) stores immutable object metadata
in Postgres and bytes through an `ObjectStore` protocol. Development Compose
uses Garage as an S3-compatible store. The cached
[get_object_store](../../backend/src/files/dependencies.py) dependency constructs
the configured adapter; inspect [files/config.py](../../backend/src/files/config.py)
for storage settings rather than copying credentials into notes or scripts.

[upload_file](../../backend/src/files/access.py) streams bytes into a new
namespaced UUID key without holding a DB session and returns an `UploadedFile`
descriptor (byte size, SHA-256, ETag). Callers then pass that descriptor to
[insert_file](../../backend/src/files/access.py) to execute a Core SQL `INSERT`
into `stored_files` inside their transaction without committing or triggering
ORM autoflush. The writer completes on context exit and attempts multipart abort
on failure. Object upload and database commit are separate operations; rolling
back SQL does not itself undo an already completed object upload. Do not
describe this as an atomic cross-store write.

Translation tasks distinguish initial inputs, provider request/output handles,
and normalized stage-output artifacts. Check the actual file field and codec
before treating downloaded bytes as normalized translation records. See
[chapter translation](chapter-translation.md) for output completeness checks.

An async store sits beside the sync one for async callers:
[async_storage.py](../../backend/src/files/async_storage.py) defines
`AsyncObjectStore` (`create` is an async context manager yielding a writer with
awaitable `write`; `fetch` is an async iterator) and `AioS3ObjectStore`, an
aiobotocore port of the multipart writer with the same part, ETag, and abort
behavior. It keeps one session and opens a client per operation, so it works from
any event loop. `get_async_object_store()` shares settings with `get_object_store()`.
aiobotocore pins botocore, which holds boto3 at a matching version (1.43.117 when
added). Delete the sync store once every caller is async.

[File access tests](../../backend/tests/files/test_access.py) cover metadata and
streamed content; [storage tests](../../backend/tests/files/test_storage.py)
exercise the adapter's upload/fetch behavior.
