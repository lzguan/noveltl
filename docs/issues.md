# Known Issues and TODO

**Last Updated**: March 7, 2026  
**Status**: Draft

This document tracks known bugs, technical debt, and planned improvements for the NovelTL platform.

---

## Table of Contents

1. [Missing `from_attributes=True` on some schemas](#missing-from_attributestrue-on-some-schemas)
2. [Broad exception handling swallows debug info](#broad-exception-handling-swallows-debug-info)
3. [Security: No rate limiting on `/token` endpoint](#security-no-rate-limiting-on-token-endpoint)
4. [Security: Consider refresh tokens](#security-consider-refresh-tokens)
5. [Performance: Multiple sessions per worker task](#performance-multiple-sessions-per-worker-task)
6. [Performance: Missing indexes](#performance-missing-indexes)
7. [Technical Debt: "Raw" prefix on Chapter models is misleading](#technical-debt-raw-prefix-on-chapter-models-is-misleading)
8. [Refactor: Replace `novel_parent_id` with Novel Relations association table](#refactor-replace-novel_parent_id-with-novel-relations-association-table)
9. [API: Pagination on list endpoints](#api-pagination-on-list-endpoints)
10. [Testing: Insufficient code coverage](#testing-insufficient-code-coverage)
11. [Planned Feature: AutoLabel Job Timeout](#planned-feature-autolabel-job-timeout)
12. [Planned Feature: Batch Inference Optimization](#planned-feature-batch-inference-optimization)
13. [Planned Features (Permissions)](#planned-features-permissions)
14. [Schema: Label Group Lineage Tracking](#schema-label-group-lineage-tracking)

---

## Missing `from_attributes=True` on some schemas

**Status**: Verified ✓

`Novel`, `RawChapter`, `RawChapterRevision` in [novels/schemas.py](../backend/src/novels/schemas.py) are missing `model_config = ConfigDict(from_attributes=True)`, which prevents Pydantic from converting SQLAlchemy ORM model instances to schema instances.

**Current State**: Only `RawChapterRevisionMeta` has this configuration (line 130).

**Impact**: Router endpoints that return these schemas directly from service layer ORM objects will fail.

**Fix**: Add to each schema:
```python
model_config = ConfigDict(from_attributes=True)
```

## Broad exception handling swallows debug info

**Status**: Verified ✓

[novels/service.py](../backend/src/novels/service.py) has 9 instances of `except Exception as e:` that catch all exceptions and raise `UnknownError`, losing the original exception context and stack trace.

**Examples**:
- Line 381: `insert_novel()` - catches everything after specific IntegrityError/DataError handling
- Line 428: `modify_novel()` - catches everything
- Line 482, 540, 589: Similar pattern in other functions

**Impact**: Makes debugging production issues difficult. Original exception types and messages are lost.

**Better Approach**: Log original exception before re-raising, or let unexpected exceptions propagate to global handler:
```python
except Exception as e:
    logger.exception(f"Unexpected error in insert_novel: {e}")
    raise UnknownError from e
```

## Security: No rate limiting on `/token` endpoint

**Status**: Verified ✓

[auth/router.py](../backend/src/auth/router.py) `POST /token` endpoint (line 26) has no rate limiting, making it vulnerable to brute force password attacks.

**Current Protection**: None visible in router or dependencies.

**Recommended Solutions**:
1. Use `slowapi` library with Redis backend for distributed rate limiting
2. Implement account lockout after N failed attempts
3. Add CAPTCHA after repeated failures
4. Monitor for suspicious login patterns

## Security: Consider refresh tokens
`ACCESS_TOKEN_EXPIRE_MINUTES = 30` is short. Refresh tokens would improve UX without compromising security.

## Performance: Multiple sessions per worker task

**Status**: Verified ✓

[autolabels/worker/tasks.py](../backend/src/autolabels/worker/tasks.py) creates 6 separate `SessionLocal()` contexts within `autolabel_infer()` task (lines 38, 47, 56, 65, 104, 112).

**Impact**: Each context acquires a new database connection from the pool. For high-throughput worker tasks, this creates unnecessary connection churn.

**Why It Happens**: Error handling - different exception paths each need to update the database, so separate sessions prevent rollback conflicts.

**Better Approach**: Use a single session with savepoints for partial rollback, or refactor to consolidate error handling.

## Performance: Missing indexes

**Status**: Verified ✓

Migration [06741dac5042_initial.py](../backend/alembic/versions/06741dac5042_initial.py) is missing indexes on frequently queried columns:

**Missing Indexes**:
1. `RawChapter.raw_chapter_num` - Used for sorting chapters (ORDER BY), not covered by composite unique constraint `(raw_chapter_num, novel_id)`
2. `Contributor.user_id` - Used in JOIN queries to find user's novels/label groups (foreign key not auto-indexed in PostgreSQL)
3. `LabelContributor.user_id` - Same issue as above

**Impact**: Sequential scans on tables with many rows. Particularly problematic for users with many novels or queries like "get all chapters for novel X ordered by chapter number".

**Fix**: Add indexes in new migration:
```sql
CREATE INDEX ix_raw_chapter_num ON raw_chapters(raw_chapter_num);
CREATE INDEX ix_novel_contributors_user_id ON novel_contributors(user_id);
CREATE INDEX ix_label_group_contributors_user_id ON label_group_contributors(user_id);
```

## Technical Debt: "Raw" prefix on Chapter models is misleading

**Status**: Planned refactoring

The models `RawChapter` and `RawChapterRevision` use the "Raw" prefix from early project design when there was a planned `TranslatedChapter` class. Since that feature was removed, the "Raw" prefix is now confusing and should be renamed.

**Proposed Changes**:
- `RawChapter` → `Chapter`
- `RawChapterRevision` → `ChapterRevision`
- Update all references in:
  - Database models (`backend/src/novels/models.py`)
  - API endpoints (currently `/chapters`, `/revisions` - done, corresponding changes in frontend done)
  - Schemas (`backend/src/novels/schemas.py`)
  - Service functions
  - Documentation

**Affected Files**:
- `backend/src/novels/models.py` - Model class names
- `backend/src/novels/schemas.py` - Schema class names
- `backend/src/novels/router.py` - Type hints
- `backend/src/novels/service.py` - Type hints and queries
- `backend/src/labels/models.py` - Foreign key relationships
- `backend/src/autolabels/models.py` - Foreign key relationships
- All documentation files
- Database migration (table rename: `raw_chapters` → `chapters`, `raw_chapter_revisions` → `chapter_revisions`)

**Impact**: This is a breaking database migration. Requires careful coordination:
1. Create migration to rename tables and columns
2. Update all code references
3. Update API response field names (breaking API change)

**Recommendation**: Schedule as part of larger refactoring before v1.0 release.

## Refactor: Replace `novel_parent_id` with Novel Relations association table

**Status**: Planned

[novels/models.py](../backend/src/novels/models.py) uses a `novel_parent_id` FK to model a single-parent tree of novels. This is too rigid (one parent, one relation type) and allows circular references (self-reference, A→B→A, deeper cycles) with no validation.

**Proposed replacement:** Drop `novel_parent_id` and add an association table:

```sql
CREATE TABLE novel_relations (
    novel_relation_id SERIAL PRIMARY KEY,
    novel_id_1 INT NOT NULL REFERENCES novels(novel_id),
    novel_id_2 INT NOT NULL REFERENCES novels(novel_id),
    relation VARCHAR NOT NULL,  -- enum/protocol TBD
    CHECK (novel_id_1 != novel_id_2)
);
```

**Design decisions needed:**

1. **Relation type protocol** — define the allowed values for `relation` and their semantics. Starting candidates:
   - `translation` — novel_id_1 is the source, novel_id_2 is its translation (directed)
   - `recommended` — symmetric suggestion between two novels
   - Others TBD (`sequel`/`prequel`?, `alternate_version`?)

2. **Directionality** — some relations are asymmetric (translation: source → target), others symmetric (recommended). Either encode this per-type in backend logic, or add a `directed: bool` column.

3. **Uniqueness** — should `(A, B, translation)` be unique? If symmetric relations enforce canonical ordering (e.g., `novel_id_1 < novel_id_2`), a unique constraint on `(novel_id_1, novel_id_2, relation)` suffices. Directed relations allow both `(A, B)` and `(B, A)`.

4. **Permission implications** — does a relation grant cross-novel access? E.g., can contributors of a source novel see a linked restricted translation? This interacts with the planned alias system (see [Planned Features: Permissions](#planned-features-permissions)).

**Affected files:** `novels/models.py` (drop `novel_parent_id`, add `NovelRelation` model), `novels/schemas.py`, `novels/service.py` (new CRUD for relations), `novels/router.py` (new endpoints), new migration.

## API: Pagination on list endpoints

**Status**: Verified ✓

List endpoints in [novels/router.py](../backend/src/novels/router.py) return all matching records without pagination:
- `GET /novels` (line 46) - No `limit`/`offset` parameters
- `GET /novels/mine` (line 66) - No pagination
- Similar issues on other list endpoints

**Current Behavior**:
```python
@router.get('/novels', response_model=list[schemas.Novel])
async def read_novels(...):
    novels = query_novels_by_title(db, current_user, title_contains)
    return novels  # Returns ALL matching novels
```

**Impact**: 
- Large response payloads for users with many novels (hundreds of KB)
- Slow queries as dataset grows
- Poor UX - frontend has to load everything upfront

**Fix**: Add pagination parameters:
```python
@router.get('/novels')
async def read_novels(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    ...
):
    novels = query_novels_by_title(db, current_user, title_contains, limit, offset)
    return novels
```

## Testing: Insufficient code coverage

**Status**: To Do

Test coverage is currently incomplete across multiple modules:

**Current State**:
- Test suite exists in `backend/tests/` with fixtures and module-specific test files
- Coverage reporting configured in `pyproject.toml` with pytest-cov
- Many modules have tests but coverage percentage not documented
- Critical paths (authentication, permissions, database operations) need verification

**Gaps**:
- No coverage threshold enforcement in CI/CD
- Edge cases and error paths may be undertested
- Integration tests exist but unit test coverage unknown
- Worker tasks (NER processing) coverage unclear

**Impact**: 
- Bugs may slip through in untested code paths
- Refactoring is riskier without comprehensive test coverage
- Difficult to assess which code is safe to modify
- Technical debt accumulates in untested areas

**Recommended Approach**:
1. Measure baseline coverage: `pytest --cov=src --cov-report=term-missing`
2. Set minimum thresholds in `pyproject.toml` (e.g., 80% overall, 90% for critical modules)
3. Add coverage reporting to CI pipeline with failure on threshold miss
4. Prioritize coverage improvements:
   - Authentication flows (login, token refresh, permissions)
   - Data validation (schema validation, circular reference checks)
   - API endpoints (error handling, edge cases)
   - Worker tasks (job processing, failure scenarios)
5. Track coverage trends over time with tools like codecov or coveralls

**Quick Start**:
```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# View detailed HTML report
open htmlcov/index.html

# Fail if coverage below 80%
pytest --cov=src --cov-fail-under=80
```

## Planned Feature: AutoLabel Job Timeout

Worker tasks that hang (OOM, model deadlock, network partition) leave AutoLabel rows stuck in `PROCESSING` forever with no recovery path.

**Proposed approach:**

1. **Add `job_timeout` to `NERModelParamsBase`** — each model's param schema inherits a `job_timeout: int` field (seconds). Defaults can differ per model based on expected inference time. The worker wraps the inference call with `asyncio.wait_for` (or `asyncio.timeout` on Python 3.11+):
   ```python
   result = await asyncio.wait_for(
       run_inference(text, params),
       timeout=params.job_timeout
   )
   ```
   On `TimeoutError`, write `status=FAILED`, `message="Job timed out."`.

2. **Add `auto_label_timeout_time` column** — store the computed deadline (`enqueued_at + job_timeout`) on the AutoLabel row so it's visible to external observers without needing to re-derive it.

3. **Cron job cleanup (lower priority)** — in case of worker crash/disconnect the `asyncio.timeout` path never runs. A cron job can sweep for rows where `auto_label_status = 'processing'` and `auto_label_timeout_time < now()`, resetting them to `PENDING` with a new `job_id` to invalidate any zombie worker that reconnects.

**Affected files:** `autolabels/constants.py` (`NERModelParamsBase`), `autolabels/worker/tasks.py`, new migration for `auto_label_timeout_time` column.

## Planned Feature: Batch Inference Optimization

**Current:** One chapter per worker job (one ARQ task per AutoLabel row).  
**Proposed:** Batch multiple chapters into a single worker task for a forward pass.

**Benefits:**
- Amortize model loading overhead (~500ms per job → ~500ms per batch)
- Better GPU utilization
- 5-10x throughput improvement at scale

**Challenges:**
- ARQ job granularity — current design is one job per `auto_label_id`; batching requires either a new job type or grouping logic at enqueue time
- Error isolation — one chapter's failure shouldn't FAIL the entire batch; need per-row error tracking within a batch job
- Variable chapter lengths affect optimal batch size

## Planned Features (Permissions)

### Alias System for Restricted Novels

Novels can have multiple aliases (e.g., Chinese title, English title). When a user creates a novel, check for matching aliases against existing restricted novels and send collaboration requests to owners of matching novels. Reduces duplicate translation efforts. See [permissions.md](permissions.md#visibility-levels) for context on Restricted visibility.

### Publicly Editable Label Groups

Label groups will support a `publicly_editable` flag. When enabled, any user can contribute labels to the group (useful for community labeling projects). Requires the parent novel to also be public. Individual label `label_dirty` flag tracks manual edits.

## Schema: Label Group Lineage Tracking

**Status:** Discussion

The `create_copy` option in `apply_filter` creates a new label group but doesn't record where it came from. We need a way to track which label group was derived from which, for provenance and potential undo.

### Option A: Simple FK on `label_groups`

Add a nullable self-referencing FK:

```
label_groups
  ...
  source_label_group_id  INTEGER  FK → label_groups  NULLABLE
```

- Copy → original backlink: `WHERE source_label_group_id = :original_id`
- Provenance chain: follow `source_label_group_id` upward to root
- Zero overhead for non-copy groups (just `NULL`)
- Simple, sufficient if copies always have exactly one source

### Option B: Association table with metadata

```
label_group_lineage
  source_label_group_id   FK → label_groups  PK
  derived_label_group_id  FK → label_groups  PK
  operation               VARCHAR             -- e.g. "score_filter_apply"
  created_at              TIMESTAMP
```

- Supports multiple sources per derived group (e.g., merging data from two groups)
- Stores what operation created the copy and when
- More flexible but heavier

### Open questions

- Is there a real use case for multiple-source derivation, or is single-parent always enough?
- Should the UI expose lineage to users (transparent) or hide it (undo/redo chain)? Leaning toward transparent — just show all groups and let the user see "copied from X."

## Relevant Files

- [backend/src/novels/schemas.py](../backend/src/novels/schemas.py) - Missing `from_attributes=True` on Novel, RawChapter, RawChapterRevision (lines 12, 75, 98)
- [backend/src/novels/service.py](../backend/src/novels/service.py) - Broad exception handling (20+ instances), circular parent validation missing in `modify_novel()` (line 386)
- [backend/src/novels/router.py](../backend/src/novels/router.py) - No pagination on list endpoints (lines 46, 66, 87, 113, etc.)
- [backend/src/auth/router.py](../backend/src/auth/router.py) - `/token` endpoint without rate limiting (line 26)
- [backend/src/autolabels/worker/tasks.py](../backend/src/autolabels/worker/tasks.py) - Multiple SessionLocal() calls (6 instances)
- [backend/alembic/versions/06741dac5042_initial.py](../backend/alembic/versions/06741dac5042_initial.py) - Migration missing performance indexes
- [backend/pyproject.toml](../backend/pyproject.toml) - pytest-cov configuration

## See Also

- [private_issues.md](private_issues.md) - Project-specific issues
- [architecture.md](architecture.md) - System architecture
- [database-schema.md](database-schema.md) - Schema design decisions
- [api-design.md](api-design.md) - API patterns (pagination, error handling)
