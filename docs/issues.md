## Bug: `insert_label_group` double `scalar_one()` call
In `src/labels/service.py`, the function calls `result.scalar_one()` twice - the second call will fail since the cursor is already consumed.

## Missing `from_attributes=True` on some schemas  
`Novel`, `RawChapter`, `RawChapterRevision` in `src/novels/schemas.py` are missing `model_config = ConfigDict(from_attributes=True)`, which may cause issues when converting from ORM models.

## Broad exception handling swallows debug info
Several service functions catch bare `Exception` and raise `UnknownError` (e.g., `src/novels/service.py`). Consider logging original exceptions before re-raising.

## Security: No rate limiting on `/token` endpoint
Brute force attacks on login are possible without rate limiting.

## Security: Consider refresh tokens
`ACCESS_TOKEN_EXPIRE_MINUTES = 30` is short. Refresh tokens would improve UX without compromising security.

## Performance: Multiple sessions per worker task
`src/autolabels/worker/tasks.py` creates multiple `SessionLocal()` contexts per task. Could consolidate to reduce connection overhead.

## Performance: Missing indexes
Consider indexes on frequently queried/filtered columns:
- `RawChapter.raw_chapter_num`
- `Contributor.user_id`

## Validation: Circular novel parent references
`UpdateNovel.novel_parent_id` could create cycles (novel pointing to itself or circular chains).

## API: Pagination on list endpoints
`/novels`, `/chapters`, `/revisions` etc. should support pagination for large datasets.