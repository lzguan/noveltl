# Background services and stored files

Code checked 2026-11-03. Use the service's own worker and progress model when
debugging; the request-result cache is a different subsystem.

## Worker map

| Work | Celery app | Broker database setting (default) | Registration |
| --- | --- | --- | --- |
| Autolabel inference | [autolabels](../../backend/src/autolabels/celery_app.py) | `AUTOLABELS_DATABASE` (1) | [dispatch/celery.py](../../backend/src/autolabels/dispatch/celery.py) |
| Filter runners | [filters](../../backend/src/filters/celery_app.py) | `FILTERS_DATABASE` (0) | [dispatch/celery.py](../../backend/src/filters/dispatch/celery.py) |
| Memory recording/naming | [memory agent](../../backend/src/memory/agent/celery_app.py) | `AGENT_DATABASE` (3) | [dispatch/celery.py](../../backend/src/memory/agent/dispatch/celery.py) |
| Chapter translation | [translations](../../backend/src/translations/celery_app.py) | `TRANSLATIONS_DATABASE` (4) | [actions package](../../backend/src/translations/actions/__init__.py) |

Defaults come from [config.py](../../backend/src/config.py); inspect actual
deployment settings when diagnosing a connection. Request-result caching uses
`REQUESTS_DATABASE` (2) via [redis_conn.py](../../backend/src/requests/redis_conn.py).
These apps do not configure a Celery result backend. Do not assume a
`celery-task-meta-*` key exists or use queue delivery as evidence of completion.
Use service persistence and worker logs for progress and failure analysis.

Autolabels, filters, and translations currently configure prefork workers with
concurrency 2; memory uses threads with concurrency 8. Each has its own
`celeryconfig.py`; a worker's concurrency is not a guarantee of concurrent
execution inside a single memory job, which is [claimed sequentially](memory-jobs.md).

The autolabel, filter, and memory publishing dispatchers use named `send_task`
calls. Their worker registration modules import the implementation. Preserve
that split when changing task contracts so API-side dispatch does not pull in
inference/runner SDKs. Chapter translation instead registers action callbacks;
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

[create_file](../../backend/src/files/access.py) streams bytes into a new
namespaced UUID key, computes byte size/SHA-256, then adds `StoredFile` metadata
to the caller's session. It does **not** commit. The writer completes on context
exit and attempts multipart abort on failure. Object upload and database commit
are separate operations; rolling back SQL does not itself undo an already
completed object upload. Do not describe this as an atomic cross-store write.

Translation tasks distinguish initial inputs, provider request/output handles,
and normalized stage-output artifacts. Check the actual file field and codec
before treating downloaded bytes as normalized translation records. See
[chapter translation](chapter-translation.md) for output completeness checks.

[File access tests](../../backend/tests/files/test_access.py) cover metadata and
streamed content; [storage tests](../../backend/tests/files/test_storage.py)
exercise the adapter's upload/fetch behavior.
