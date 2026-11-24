# Short-term plan (2026-11-24)

The user's working list, in agreed order, with status. Proposals here are
discussed directions, not approved designs, unless marked agreed. Update the
status when an item lands; remove an item once it is merged and stable.

Working rules agreed for this list: one slice per commit, the user reviews each
commit; HTTP requests must return fast and long work goes to a worker; no
heavy processing in the backend container.

## 1. Async backend (partly merged in #144)

Done, one commit each: psycopg 3 driver swap (psycopg exception classes such
as `UniqueViolation` instead of SQLSTATE strings), async engine and
`get_async_db` (`expire_on_commit=False`), then `languages`, `auth` (password
hashing via `asyncio.to_thread`; the auth dependencies use the async session, so
unconverted services briefly use two connections per request), `novels` with
`editing` and the glossary `GET /terms` query, and `labels`.

Done on `feature/taskiq-agent-workers`: the whole memory module (routes, services,
access layer, agent tools, task bookkeeping, workers) is on async sessions, and the
memory agent worker runs on taskiq. The translation and autolabel routes now use async sessions.
Autolabel inference dispatch still uses the Celery dispatcher. Remaining: slice 2
(translations worker).

- Deferred (user decision, 2026-11-23): `filters` stays sync; the user does not
  use it. Sync routes run in the threadpool, so the only costs are a second
  connection per request and keeping sync paths in shared helpers (notably
  `src/filters/permissions.py`). When it is converted, prefer converting
  `src/filters/lifecycle.py` together with its worker; until then the fallback
  is `await db.run_sync(...)` from async code.
- Memory agent worker on taskiq (branch `feature/taskiq-agent-workers`): the Celery
  implementation stays alongside (`celery_app.py`, `dispatch/celery_worker.py`); pick one in
  `dispatch/dependencies.py` and the Dockerfile. Known pre-existing bug: read
  toolsets are not `sequential=True`, so parallel read calls share one session
  across threads.
- Slice 2 PR A done on `feature/translations-async-steps` (2026-11-23): steps,
  clients, storage, inputs, `create_job` and all tests on async sessions;
  `src/streaming.py` deleted.
- Slice 2 PR B on `feature/translations-taskiq`: taskiq worker and scheduler,
  `celery` / `taskiq` dependency groups per image (only the API syncs both).
  Steps no longer hold a connection or transaction across I/O; mid-step lease
  renewal is gone (`renew_lease` removed); steps must fit the 300 s lease.
  Remaining: load test and profile against the pooled engine, remove remaining
  `asyncio.run` bridges in `translations/actions/execution/celery_actions.py`
  and `translations/clients/sync_client.py`, and decide whether the in-process
  `AsyncActionCallbacks` path stays.
- Rejected: `asyncio.run` from sync code into async functions; sync duplicates
  of shared readers.
- Test pitfalls: async test engine needs `NullPool` (TestClient runs its own
  loop); a test that expires its sync session after a route deleted a row
  through the async session must read ids before `expire_all()`.

## 2. Autolabel promotion & autolabels UI (merged through #154; eager promotion on `feature/wave2-permissions-eager-publish`)

- Merged: background promotion jobs (#144), promotion sweeper (#151), frontend
  autolabel runs/preview/polling UI refactor (#154; see [Autolabels UI](autolabels-ui.md)).
- Done on `feature/wave2-permissions-eager-publish`: eager autolabel promotion.
  Promotion always reuses existing `LabelData` rows (creating one only if
  missing). `skip_existing_labels` (persisted on `label_promotion_jobs` via
  migration `d7e2a94c1b51`, default `True`) controls whether chapters with at
  least one attached `Label` are skipped; when `False`, non-overlapping
  autolabels are inserted while existing overlapping labels win. Exposed on
  `PromoteAutoLabelDialog`.
- Open PR (kept separate intentionally): `fix/promotion-reload-races` (rebase
  onto `master` when ready).
- Remaining follow-up: test fixtures (`tests/fixtures/scenarios.py`) and three
  integration tests still seed through `insert_label_datas_by_autolabels`; move
  them to the job path, then delete it and `CreateLabelDataByAutoLabelStatus`.
  Small open choice: count in-flight POSTs in `queue`'s cap check.

## 3. Label permission refactor (PR 1 merged in #152; PR 2 on `feature/wave2-permissions-eager-publish`)

- Merged in #152: label permission helpers decide from novel role only, label
  group creation stopped inserting `LabelContributor` rows, and `filters`
  workflow checks were updated.
- Done on `feature/wave2-permissions-eager-publish`: dropped
  `label_group_contributors` (migration `c2b4f81a9d30`), removed
  `LabelContributor`, `LabelRole`, `LabelGroupWithRole`,
  `GET /label-groups-with-role`, `GET /label-groups/{id}/contributors`, and
  collapsed `novel_edit_only`/`label_edit_only` to `edit_only`. Frontend
  switched to `GET /label-groups` and novel `Role`.

## 4. Bulk chapter publish (on `feature/wave2-permissions-eager-publish`)

- Done on `feature/wave2-permissions-eager-publish`:
  `POST /novels/{novelId}/chapters/visibility` (inclusive `start`/`end` range
  or all chapters when omitted, single permission-wrapped `UPDATE ... RETURNING
  chapter_num`), subtle public/private icons in `ChapterPanel`,
  `BulkChapterVisibilityDialog`, and `useChapters.setChaptersVisibility`.

## 5. Reader feedback and mascot

Feedback endpoint and unintrusive reader UI (mobile and desktop); a mascot.
Open questions: anonymous submission and rate limiting (the reader has no
login), anchoring to a chapter content version with character offsets,
progressive enhancement (the reader works without JavaScript), and export to
the analytics store as a `reader_feedback.v1` kind.

## Smaller follow-ups

- Bulk chapter upload (on `chore/wave2-quick-cleanup`): kept synchronous;
  `ValidationError` now returns 422 via `RequestValidationError` without
  echoing `input`/`url`, and `upload_v1` chunks DB inserts in batches of 1000.
- CI Playwright report upload (on `chore/wave2-quick-cleanup`): changed
  `.github/workflows/test-e2e.yml` to `if: ${{ !cancelled() }}` so traces from
  flakes that pass on retry are uploaded.
- Backend test suite pruning: audit redundant/slow tests when convenient.
- E2E and backend pytest both use `test_db`, and the e2e seed drops all tables;
  never run them at the same time.
