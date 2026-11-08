# Editor persistence and request recovery

Code checked 2026-11-03. This note covers the persistence boundary; detailed
rendering and text-model documentation remains in the existing human docs.

## Entry points

| Responsibility | Source |
| --- | --- |
| User events and manager composition | [controller.ts](../../frontend/src/edit/controller/controller.ts) |
| Optimistic chapter state and request construction | [chapterDataManager.ts](../../frontend/src/edit/controller/chapterDataManager.ts) |
| Provisional/server IDs and reservations | [idRepository.ts](../../frontend/src/edit/controller/idRepository.ts) |
| Sending, polling, retry scheduling | [requestmanager.ts](../../frontend/src/edit/controller/requestmanager.ts) |
| Request contracts and recovery helpers | [requestTypes.ts](../../frontend/src/edit/controller/types/requestTypes.ts) |
| Version creation and label porting | [novels/service.py](../../backend/src/novels/service.py) |
| Label operation streams | [labels/service.py](../../backend/src/labels/service.py) |
| Request result caching | [decorators.py](../../backend/src/requests/decorators.py), [cache.py](../../backend/src/requests/cache.py) |

## Revision identity matters

Text edits call `modify_chapter_content` with both a chapter ID and the content
revision the client edited. The service requires that content ID to be current;
stale revisions are rejected rather than applied to whichever text is latest.
Successful edits insert a new `ChapterContent` revision, not an in-place update.

Text operations also transform labels. The service ports **all** label-data
groups on the old revision, including groups the caller cannot view and groups
with zero labels. Its response returns the new content ID/version and a map of
old to new label-data IDs. New label rows get new IDs. Treat this response as a
change of identities when updating client reservations and subsequent requests.

Label-only streams operate against a label-data ID's content revision. They
apply their operations in one transaction and roll back on failure. Keep range,
overlap, permission, and concurrent-update errors distinct from transport errors.
The SQL permission modifiers in [novels](../../backend/src/novels/permissions.py)
and [labels](../../backend/src/labels/permissions.py) are authoritative; hiding a
control in the UI does not implement access control.

## A timeout is an unknown result

Some editor mutations accept `requestKey` and use `ttl_cache`/`attl_cache`.
The decorator atomically reserves a pending cache entry with Redis `SET NX`,
then stores success or failure. Reusing a reserved key returns a cache-conflict
409; it does not automatically replay the cached response. With no key the
function runs without this cache. These are expiring request-result entries,
not durable job records or an exactly-once transaction system.

The request manager reserves provisional IDs before sending work and holds
those reservations during recovery. On a cached request timeout it polls
`GET /cached/{id}` with the same key before resending a mutation whose outcome
is unknown. A successful pending poll does not consume a retry. Missing cache
entries and cache conflicts regenerate keys for retries; connection errors
retain the current key. Uncached timeouts follow the resend path. Use the actual
`requeueRequest` implementation rather than inferring every transition from the
file's introductory comments.

Polling uses per-request scheduled delays, with a capped backoff. Requests and
queries have transport timeouts, and exhausted retries invoke failure handling
and release reservations. Changing timing must preserve dependency ordering and
the distinction between pending, cache conflict, and a failed mutation.

## Jumping to a text range

`chapterMgr.switchChapter(chapterId, { start, end, desiredCCId? })` opens a
chapter and highlights a range. The highlight applies only when the loaded
content's server ID equals `desiredCCId`; when `desiredCCId` is undefined
(`novelDataManager` `openChapter`), it applies to whatever version loads, so
offsets from an older version can highlight the wrong span. A mismatch raises
`chapterOpened` with `validCCId: false`, which nothing surfaces to the user yet.

Server-side callers should go through `gotoText` in `EditNovelPage`, shared by
Filters and term search, which maps `ccServId` to `desiredCCId`. Until
2026-11-06 Filters passed `{ start, end, ccServId }` directly, so the version
check never ran; structural typing accepted the wrong field name because
`desiredCCId` is optional.

Proposed, not done (the user prefers not to change the controller for now):
make `desiredCCId` required whenever a highlight is passed, so a missing or
misnamed version fails the type check, and add a `chapterManager` test that a
mismatched version opens without a highlight. Every current position source
(filter results, term search, labels, memories) already carries a content
version. The check compares server versions, so local edits not yet synced can
still shift a highlight that passes it.

## Regression entry points

- [Unicode offset E2E cases](../../e2e/tests/editor-unicode-offsets.spec.ts)
  reproduce insertion persistence, deletion validation, server-label rendering,
  and search-preview highlighting after supplementary Unicode characters. The
  frontend uses UTF-16 offsets while backend slicing uses code-point offsets;
  the tests assert correct behavior and fail until the conversions are fixed.
  The four defects were reproduced against real browser/API/database boundaries
  on 2026-11-08. The E2E seed reflects existing tables before dropping them so
  leftover tables from other checkouts do not block the reset.
- [Request manager](../../frontend/src/edit/controller/__test__/requestmanager.test.ts) and [ID repository](../../frontend/src/edit/controller/__test__/idRepository.test.ts).
- [Novel services](../../backend/tests/novels/test_novels_service.py) and [permissions](../../backend/tests/novels/test_novels_permissions.py).
- [Label streams](../../backend/tests/labels/test_label_stream.py).
- [Cache contract](../../backend/tests/requests/test_requests.py) and [real Redis](../../backend/tests/requests/test_redis_cache_integration.py).
