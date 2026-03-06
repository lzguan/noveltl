# Known Issues and TODO

**Last Updated**: March 5, 2026  
**Status**: Draft

This document tracks known bugs, technical debt, and planned improvements for the NovelTL platform.

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

[novels/service.py](../backend/src/novels/service.py) has 20+ instances of `except Exception as e:` that catch all exceptions and raise `UnknownError`, losing the original exception context and stack trace.

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
  - API endpoints (currently `/chapters`, `/revisions` - already using simplified names)
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

## API Design: Inconsistent endpoint kebab-case usage

**Status**: Planning

API endpoints partially follow kebab-case convention but have inconsistencies:

**Current State**:
- ✅ `/auto-labels/{id}` - kebab-case
- ✅ `/label-groups/{id}` - kebab-case
- ❌ `/chapters/{id}` - missing "raw-" prefix for consistency
- ❌ `/revisions/{id}` - missing "chapter-" for clarity

**Proposed Changes** (if pursuing full kebab-case consistency):
- `/chapters/{id}` → `/raw-chapters/{id}` (or `/chapters/{id}` after renaming RawChapter)
- `/revisions/{id}` → `/raw-chapter-revisions/{id}` (or `/chapter-revisions/{id}`)
- `/novels/{novel_id}/chapters` → `/novels/{novel_id}/raw-chapters`
- `/novels/{novel_id}/revisions` → `/novels/{novel_id}/raw-chapter-revisions`
- `/chapters/{id}/revisions` → `/raw-chapters/{id}/revisions`

**Alternative**: Keep current simplified endpoints (`/chapters`, `/revisions`) and update documentation to reflect that kebab-case is preferred but simplified names are used for commonly-accessed resources.

**Impact**: Breaking API change. Frontend code would need updates.

**Recommendation**: Decide on convention before implementing RawChapter → Chapter rename. Either:
1. Rename models first, then use `/chapters` and `/chapter-revisions` (cleaner)
2. Keep current endpoints and document as intentional simplification

## Validation: Circular novel parent references

**Status**: Verified ✓

[novels/service.py](../backend/src/novels/service.py) `modify_novel()` (line 386) accepts `novel_parent_id` without validation, allowing:
1. **Self-reference**: Novel X → parent = X
2. **Circular chains**: Novel A → parent = B, Novel B → parent = A
3. **Deep cycles**: A → B → C → A

**Current Code**:
```python
stmt = update(models.Novel).where(...).values(
    request.model_dump(exclude_unset=True)  # No validation
)
```

**Impact**: Could break traversal logic, cause infinite loops in parent chain queries, or violate business logic assumptions.

**Fix**: Add validation before update:
```python
if request.novel_parent_id == novel_id:
    raise ValueError("Novel cannot be its own parent")
# Check for cycles by traversing parent chain
```

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
