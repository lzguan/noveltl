# Background Jobs System

**Last Updated**: March 5, 2026  
**Status**: Draft

This document describes the AutoLabel background processing system - a distributed framework for running ML inference on chapter text with race condition handling, job deduplication, and automatic retries.

## Overview

The AutoLabel system processes computationally expensive NER (Named Entity Recognition) tasks asynchronously using a worker queue architecture. It handles:
- **Long-running tasks** - ML inference can take 5-30 seconds per chapter
- **Concurrent requests** - Multiple users labeling the same content
- **Result caching** - Avoid redundant inference for same (chapter, model, params)
- **Failure recovery** - Graceful handling of errors and timeouts

## Architecture

### Component Diagram

```
┌─────────────────┐      ┌─────────┐      ┌──────────┐      ┌──────────┐
│  FastAPI Server │─────▶│  Redis  │─────▶│  Worker  │─────▶│ Database │
│   (backend)     │      │  Queue  │      │ (ARQ)    │      │ (Postgres)│
└─────────────────┘      └─────────┘      └──────────┘      └──────────┘
       │                                          │                │
       └──────────────────────────────────────────┴────────────────┘
                    (Shared Database Access)
```

### Communication Flow

1. **Client Request** → Backend API (`POST /auto-labels`)
2. **Backend** → Creates/updates `AutoLabel` records in database
3. **Backend** → Enqueues job to Redis with unique `job_id`
4. **Worker** → Polls Redis queue and picks up job
5. **Worker** → Validates job still needed (via `job_id` matching)
6. **Worker** → Runs ML inference in background thread
7. **Worker** → Writes results back to database (atomic update)

## Interfaces and Abstractions

The autolabeling system uses Protocol-based abstractions for dependency injection, testability, and extensibility.

### AutoLabelDispatcher Protocol

Abstracts job queue operations. The backend doesn't know whether jobs go to Redis, RabbitMQ, or an in-memory queue.

**Protocol** ([autolabels/utils.py](../backend/src/autolabels/utils.py)):
- `async def enqueue(job_id, auto_label_id, model_name, model_params) -> None`
- Raises `QueueFullException` or `EnqueueFailedException`

**Implementation:** `ArqDispatcher` wraps ARQ/Redis, handling connection errors, timeouts, and OOM conditions.

**Usage:** Injected via FastAPI dependency `get_arq_dispatcher()`.

**Benefits:** Swappable implementations for testing (mock dispatcher) or migrating queue systems.

### NERModel Protocol

Abstracts ML model inference. Workers don't depend on specific implementations (HuggingFace, spaCy, custom models).

**Protocol** ([autolabels/worker/interfaces.py](../backend/src/autolabels/worker/interfaces.py)):
- Generic type `NERModel[P]` where `P` is model-specific parameter schema
- Attributes: `model_name`, `is_deterministic`
- Methods:
  - `predict(text, params) -> tuple[list[Label], Any]` - Run inference, return labels + metadata
  - `get_tokenizer() -> Tokenizer` - Get associated tokenizer
  - `normalize(text) -> str` - Normalize text for comparison
  - `validate(params) -> NERModelParamsBase` - Validate raw parameter dict

**Implementation:** `CluenerModel` wraps HuggingFace transformers pipeline.

**Model Registry:** `get_ner_model(model_name)` retrieves cached model instances. Models are lazy-loaded and cached for worker lifetime.

**Adding Models:** Define parameter schema, implement `NERModel[YourParams]` protocol, register in `model_cache`.

### Tokenizer Protocol

Abstracts text tokenization for chunk size calculations.

**Protocol** ([autolabels/worker/interfaces.py](../backend/src/autolabels/worker/interfaces.py)):
- `tokenize(text) -> list[str]` - Split text into tokens
- `tokenize_words(text) -> list[tuple[str, int]]` - Split into (word, token_count) pairs

**Purpose:** ML models have token limits (e.g., 512 for BERT). Tokenizer helps `chunk_text()` split at semantic boundaries while respecting limits.

### Text Chunking Utilities

**Problem:** BERT-based models have 512-token limit. Chapters can be 5000+ characters.

**Solution:** `chunk_text()` ([autolabels/worker/utils.py](../backend/src/autolabels/worker/utils.py)) splits text using separator priorities:
- `HIGH`: Paragraph breaks (`\n\n`)
- `MED`: Sentence endings (`。`, `！`)
- `LOW`: Line breaks (`\n`)

Returns `[(chunk_text, start_offset), ...]` for offset tracking when re-mapping label positions.

**Key Insight:** Preserves entity boundaries by preferring paragraph/sentence breaks over arbitrary mid-text splits.


## State Machine (AI generated, may be inaccurate)

Each `AutoLabel` record transitions through four states:

```
          ┌─────────┐
          │ PENDING │◀─────── Initial state or retry
          └────┬────┘
               │ (Worker picks up job)
               ▼
        ┌─────────────┐
        │ PROCESSING  │
        └──────┬──────┘
               │
         ┌─────┴─────┐
         │           │
         ▼           ▼
    ┌──────┐    ┌────────┐
    │ DONE │    │ FAILED │
    └──────┘    └────────┘
```

### State Definitions

- **PENDING** - Job queued, waiting for worker pickup
- **PROCESSING** - Worker actively running inference
- **DONE** - Inference completed successfully, results stored in `auto_label_data`
- **FAILED** - Inference failed (validation error, model error, timeout, etc.)

### State Transitions

| From | To | Trigger | Notes |
|------|----|---------| ------|
| `None` | `PENDING` | User requests autolabel for first time | New record created |
| `PENDING` | `PROCESSING` | Worker claims job | Worker acquired lock |
| `PROCESSING` | `DONE` | Inference succeeds | Results written to DB |
| `PROCESSING` | `FAILED` | Inference fails | Error message in `auto_label_message` |
| `FAILED` | `PENDING` | User manually retries | Fresh job_id generated |
| `DONE` | `PENDING` | User force re-runs (rare) | Overwrites cached result |
| `PENDING` | `PENDING` | Duplicate request within rate limit | No change, request rejected |
| `PROCESSING` | `PROCESSING` | Stale worker update | No change (job_id mismatch, update affects 0 rows) |

## Concurrency Control

### The Race Condition Problem

AutoLabel requests face multiple concurrency challenges:

**Scenario 1: Double-Submit**
```
User clicks "Autolabel" twice rapidly
→ Two requests create two jobs for same chapter
→ Without protection: both workers run inference, wasting compute
```

**Scenario 2: Stale Worker**
```
Worker 1 picks up job_id=A at t=0
User retries at t=1, creates job_id=B
Worker 2 starts job_id=B, completes first
Worker 1 completes later with job_id=A
→ Without protection: Worker 1 overwrites Worker 2's results
```

**Scenario 3: Distributed Workers**
```
Multiple worker containers in production
Worker 1 and Worker 2 both poll Redis simultaneously
Both pick up same job
→ Without protection: duplicate work
```

### Solution: Optimistic Locking with Job IDs

Every job request generates a unique `job_id` (UUID v4). All database updates use this as an optimistic lock:

```python
# From backend/src/autolabels/worker/tasks.py
base_update = update(AutoLabel).where(
    AutoLabel.auto_label_id == auto_label_id
).where(
    AutoLabel.auto_label_last_job_id == job_id  # ← Optimistic lock
)
```

**Critical Insight:** If the worker's `job_id` doesn't match the database, the `UPDATE` statement affects 0 rows:

```python
result = db.execute(stmt)
if result.rowcount == 0:
    # Job ID mismatch - another worker already updated this, or job was cancelled
    return  # Exit silently without error
```

This prevents:
- Overwriting newer results with stale data
- Multiple workers processing identical jobs
- Data corruption from race conditions

### Example: Optimistic Lock in Action

```
t=0: User requests autolabel
     DB: auto_label_id=42, job_id=NULL, status=PENDING
     Backend: job_id=A, enqueue to Redis
     DB UPDATE: job_id=A, status=PENDING

t=1: Worker 1 picks up job_id=A
     DB UPDATE: WHERE job_id=A → status=PROCESSING ✅ (1 row updated)

t=2: User clicks retry
     Backend: job_id=B, enqueue to Redis
     DB UPDATE: job_id=B, status=PENDING

t=3: Worker 2 picks up job_id=B
     DB UPDATE: WHERE job_id=B → status=PROCESSING ✅ (1 row updated)

t=4: Worker 2 completes inference
     DB UPDATE: WHERE job_id=B → status=DONE, results=... ✅ (1 row updated)

t=5: Worker 1 completes inference (slower)
     DB UPDATE: WHERE job_id=A → status=DONE, results=... ❌ (0 rows updated)
     Worker 1 detects rowcount==0, exits silently
```

Worker 2's results are preserved, Worker 1's stale results are discarded.

## Deduplication Strategy

**Problem:** Users might request autolabels for the same chapters multiple times.

**Solution:** Unique constraint on `(raw_chapter_revision_id, auto_label_model_name, auto_label_model_params)`

From `backend/src/autolabels/service.py`:

```python
# Check if autolabel already exists before inserting
q = q.where(not_(exists(select(AutoLabel).where(and_(
    AutoLabel.raw_chapter_revision_id == RawChapterRevision.raw_chapter_revision_id,
    AutoLabel.auto_label_model_name == request.auto_label_model_name,
    AutoLabel.auto_label_model_params == request.auto_label_model_params
)))))
```

**Prevents:**
- Duplicate autolabel records for same (chapter, model, params)
- Queue buildup from repeated requests
- Wasting worker resources on identical jobs

**Behavior:**
- If autolabel already exists (any status), it won't be created again
- Users can check existing autolabel status via `GET /auto-labels/{auto_label_id}` or `GET /auto-labels?novel_id=...`
- To retry failed jobs, future implementation will add explicit retry endpoint

## Failure Handling

### Validation Errors

Caught before inference begins:

```python
try:
    ner_model = get_ner_model(model_name)
    params = ner_model.validate(model_params)
except ValidationError as e:
    # Mark FAILED with descriptive message
    stmt = base_update.values(
        auto_label_status=AutoLabelProgress.FAILED,
        auto_label_message=f"'{model_name}' is not a valid model name."
    )
    db.execute(stmt)
    db.commit()
    raise e  # Re-raise for logging
```

**Common validation failures:**
- Invalid model name
- Missing required parameters
- Parameter type mismatch

### Inference Errors

Caught during ML model execution:

```python
try:
    result = await ner_model.infer(text, params)
except Exception as e:
    stmt = base_update.values(
        auto_label_status=AutoLabelProgress.FAILED,
        auto_label_message=str(e)
    )
    db.execute(stmt)
    db.commit()
    raise e
```

**Common inference failures:**
- Out of memory (long chapters, large models)
- Model loading errors
- Invalid text encoding

### Database Connection Failures

If database connection fails during result write:
- Transaction rolls back automatically
- Job remains in `PROCESSING` state
- User can manually retry or wait for timeout recovery (future feature)

### Network/Redis Failures

If Redis connection fails:
- Backend rejects request with 503 Service Unavailable
- Existing jobs in queue unaffected
- Workers continue processing queued jobs

## Performance Characteristics

### Latency Breakdown

| Phase | Duration | Notes |
|-------|----------|-------|
| Request → Queue | 5-10ms | Database write + Redis enqueue |
| Queue → Worker Pickup | 100ms-2s | Depends on worker polling interval |
| Inference | 500ms-30s | Varies by chapter length (1K-10K chars), model size |
| Result Write | 10-50ms | Database update with JSONB write |

**Total:** 500ms to 32 seconds, depending on chapter length and queue depth.

### Throughput

- **Bottleneck:** ML inference (GPU/CPU bound)
- **Single worker:** 2-120 chapters/minute (depends on model)
- **Scalability:** Linear with number of worker containers

### Scaling Strategies

**Horizontal Scaling:**
- Workers are stateless - add more containers
- Redis handles 100k+ jobs/second easily
- Database can handle many worker connections

**Vertical Scaling:**
- Larger GPU → faster inference (2-10x speedup)
- More CPU cores → parallel batch processing

**Not implemented (future):**
- Worker pools with different model types
- Priority queues for urgent vs. batch jobs

## Data Model

### AutoLabel Table Schema

```python
class AutoLabel(Base):
    auto_label_id: int  # Primary key
    auto_label_data: list[dict]  # JSONB - ML inference results
    auto_label_model_name: str  # e.g., "dslim/bert-base-NER"
    auto_label_model_params: dict  # JSONB - model hyperparameters
    auto_label_status: AutoLabelProgress  # State machine
    auto_label_last_job_id: str  # UUID for optimistic locking
    auto_label_message: str | None  # Error messages for FAILED state
    raw_chapter_revision_id: int  # Foreign key to chapter
```

### Unique Constraint: Result Caching

```python
UniqueConstraint(
    raw_chapter_revision_id, 
    auto_label_model_name, 
    auto_label_model_params, 
    name="uq_model_name_params"
)
```

**Ensures:** One autolabel per (chapter, model, params) tuple. Running the same model with identical parameters on the same chapter returns the cached result instead of re-running inference.

**Example:**
```sql
-- First request: creates new record
INSERT INTO auto_labels (revision_id=123, model='bert-ner', params='{}')

-- Second request (same chapter, model, params): returns existing
SELECT * FROM auto_labels WHERE revision_id=123 AND model='bert-ner' AND params='{}'
-- If status=DONE, return results immediately
-- If status=PENDING/PROCESSING, inform user job is in progress
-- If status=FAILED, allow retry
```

### JSONB Data Format

**auto_label_data** - Array of entity dictionaries:
```json
[
  {"word": "张三", "start": 10, "end": 12, "entity_group": "PER", "score": 0.95},
  {"word": "北京", "start": 20, "end": 22, "entity_group": "LOC", "score": 0.89}
]
```

**auto_label_model_params** - Model-specific configuration:
```json
{
  "aggregation_strategy": "simple",
  "threshold": 0.5,
  "device": -1
}
```

## Testing Challenges

### Problem: Isolated Test Environment

Tests require:
- Separate test database (`test_db` instead of `db`)
- Separate Redis database (Redis DB `1` instead of `0`)
- Isolated worker process

But worker imports `SessionLocal` from `src.autolabels.worker.config`, which hardcodes connection to production database.

### Solution: Monkeypatching

From `docs/concepts/monkeypatching.md`:

```python
# In tests/conftest.py
import src.autolabels.worker.tasks as tasks_module

# Replace module-level SessionLocal with test version
tasks_module.SessionLocal = test_session_maker
```

This replaces the worker's database connection **before** tasks execute, enabling isolated testing.

**See:** [concepts/monkeypatching.md](concepts/monkeypatching.md) for detailed explanation.

## Future Enhancements (ideas by Claude)

### 1. Progress Tracking

**Current:** Binary `PROCESSING` state  
**Proposed:** Granular progress percentage (10%, 25%, 50%, 75%, 90%, 100%)

**Implementation:** Worker periodically updates `auto_label_progress_pct` field during inference:
```python
for i, chunk in enumerate(text_chunks):
    result = model.infer(chunk)
    progress = int((i+1) / len(chunks) * 100)
    db.execute(update(AutoLabel).values(progress_pct=progress))
```

### 2. Automatic Timeout Recovery

**Current:** Manual retry only for stuck jobs  
**Proposed:** Auto-retry if `PROCESSING` > 5 minutes with no update

**Implementation:** 
- Cron job checks `updated_at` timestamp
- If `status=PROCESSING` and `updated_at < now() - 5min`, reset to `PENDING`
- Generates new `job_id` to invalidate stale worker

### 3. Redis Result Caching

**Current:** Results only in PostgreSQL database  
**Proposed:** Also cache in Redis for ultra-fast retrieval

**Benefits:**
- Sub-millisecond cache hits (vs. 10-50ms DB query)
- Reduced DB load for frequently accessed results

**Trade-offs:**
- Memory usage (Redis RAM vs. Postgres disk)
- Cache invalidation complexity

### 4. Batch Inference Optimization

**Current:** One chapter per inference call  
**Proposed:** Batch multiple chapters in single forward pass

**Benefits:**
- Amortize model loading overhead (~500ms per job → ~500ms per batch)
- Better GPU utilization (batch processing)
- 5-10x throughput improvement

**Challenges:**
- Variable chapter lengths (batching strategy)
- Error isolation (one failure shouldn't fail entire batch)

## API Endpoints

### Create AutoLabel Request

```http
POST /auto-labels
Authorization: Bearer <token>
Content-Type: application/json

{
  "novel_id": 1,
  "auto_label_model_name": "cluener",
  "auto_label_model_params": {"chunk_size": 500},
  "raw_chapter_revision_ids": [1, 2, 3, 4, 5]
}

Response: 200 OK
[
  {"auto_label_id": 10, "status": "pending", "auto_label_message": "Job queued."},
  {"auto_label_id": 11, "status": "pending", "auto_label_message": "Job queued."}
]
```

**Query Parameters (all optional):**
- `raw_chapter_ids` - Filter by raw chapter IDs
- `raw_chapter_revision_ids` - Filter by specific revision IDs
- `start` - Start chapter number (inclusive)
- `end` - End chapter number (exclusive)
- `is_primary` - Filter by primary revision flag
- `is_public` - Filter by public revision flag

**Behavior:**
- Only creates autolabels for revisions that don't already have one for the given (model, params)
- Skips revisions user doesn't have access to (permission filtered)
- Only processes `is_final=true` revisions

### Query AutoLabel by ID

```http
GET /auto-labels/{auto_label_id}
Authorization: Bearer <token>

Response: 200 OK
{
  "auto_label_id": 10,
  "auto_label_status": "done",
  "auto_label_data": [
    {"word": "张三", "start": 10, "end": 12, "entity_group": "PER", "score": 0.95}
  ],
  "auto_label_model_name": "cluener",
  "auto_label_model_params": {"chunk_size": 500},
  "auto_label_message": null,
  "raw_chapter_revision_id": 1,
  "auto_label_last_job_id": "a1b2c3d4-..."
}
```

### Query AutoLabels for Novel

```http
GET /auto-labels?novel_id=1&model_names=cluener
Authorization: Bearer <token>

Response: 200 OK
{
  "1": {
    "auto_label_id": 10,
    "auto_label_status": "done",
    "auto_label_model_name": "cluener",
    "auto_label_model_params": {"chunk_size": 500},
    "raw_chapter_revision_id": 1,
    "auto_label_last_job_id": "...",
    "auto_label_message": null
  }
}
```

**Query Parameters:**
- `novel_id` (required) - Novel to query autolabels for
- `raw_chapter_ids` (optional) - Filter by chapter IDs
- `raw_chapter_revision_ids` (optional) - Filter by revision IDs
- `start` (optional) - Start chapter number
- `end` (optional) - End chapter number  
- `model_names` (optional) - Filter by model names

**Note:** Returns lightweight metadata without `auto_label_data` for performance.

## Relevant Files

- `backend/src/autolabels/models.py` - AutoLabel ORM model
- `backend/src/autolabels/service.py` - API business logic, rate limiting
- `backend/src/autolabels/router.py` - FastAPI endpoints
- `backend/src/autolabels/worker/tasks.py` - ARQ worker task implementation
- `backend/src/autolabels/worker/config.py` - Worker database connection
- `backend/src/autolabels/worker/interfaces.py` - NER model interface
- `backend/src/autolabels/constants.py` - AutoLabelProgress enum
- `backend/src/redis.py` - Redis connection management
- `compose.yaml` - Worker service definition
- `tests/autolabels/` - AutoLabel tests with monkeypatching

## See Also

- [architecture.md](architecture.md) - Service communication overview
- [database-schema.md](database-schema.md) - AutoLabel table schema
- [api-design.md](api-design.md) - AutoLabel API endpoints
- [concepts/monkeypatching.md](concepts/monkeypatching.md) - Testing worker isolation
- [issues.md](issues.md) - Known issues (worker session management, etc.)
