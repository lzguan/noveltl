# Short-term plan (2026-11-22)

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
  `src/filters/permissions.py` during the label permission refactor). When it is
  converted, prefer converting `src/filters/lifecycle.py` together with its
  worker; until then the fallback is `await db.run_sync(...)` from async code.
- Memory agent worker on taskiq (branch `feature/taskiq-agent-workers`): the Celery
  implementation stays alongside (`celery_app.py`, `dispatch/celery_worker.py`); pick one in
  `dispatch/dependencies.py` and the Dockerfile. Profiled 48 concurrent fake-model tasks with
  Tachyon: ~80% of the event loop's busy time is sync psycopg waits, two-thirds of it in
  `publish_workspace`; pydantic-ai runs sync tools in anyio worker threads (pool sized 40 to
  match). Next: convert memory services, toolsets, transaction helpers and task bookkeeping to
  `AsyncSession` (one commit per layer). Known pre-existing bug: read toolsets are not
  `sequential=True`, so parallel read calls share one session across threads.
- Slice 2 plan (agreed 2026-11-23), commit by commit with review stops. PR A: async
  `ActionTaskContext` (`AsyncSession`, async `renew_lease`) and awaitable step callbacks;
  async runner; async `BatchJobClient` (Qwen on `AsyncOpenAI` spooling uploads to a temp
  file, OpenRouter on `httpx2.AsyncClient`, `SyncChatClient` without `asyncio.run`); async
  `create_file` on `AsyncObjectStore` with `store_lines` keeping its temp file; async step
  bodies and inputs; Celery keeps running steps via one `asyncio.run` + `NullPool` engine.
  PR B: `TaskiqActionCallbacks` with polls delayed through the taskiq scheduler
  (`RedisScheduleSource` + `taskiq scheduler` service), broker on `TRANSLATIONS_DATABASE`,
  Celery still selectable, in-process `AsyncActionCallbacks` kept. Lease semantics
  unchanged (cooperative renewal between awaits).
- Slice 2 PR A done on `feature/translations-async-steps` (2026-11-23): steps,
  clients, storage, inputs, `create_job` and all tests on async sessions;
  `src/streaming.py` deleted. Known limit: the Qwen upload runs without lease
  renewal (see chapter-translation notes); add a renew hook to `create_batch_job`
  if uploads approach the 300 s submit lease.
- Slice 2 PR B on `feature/translations-taskiq`: taskiq worker and scheduler,
  `celery` / `taskiq` dependency groups per image (only the API syncs both).
  Next: load test and profile against the pooled engine.
- Future option (2026-11-24): release the step's connection while awaiting provider
  I/O. Today `run_claimed_step` keeps one transaction open across the callback, so
  concurrency per worker is bounded by connections (2 per step), long idle-in-
  transaction sessions hold back vacuum, and PgBouncer transaction pooling would
  not help. Needs a step-contract change (the wrapper owns the transaction).
- Slice 2 (translations worker to taskiq) also removes the `asyncio.run` bridges left by
  `de11687` in `translations/actions/execution/celery_actions.py` and
  `translations/clients/sync_client.py`.
  Open question for slice 2: an async taskiq worker already runs many translation jobs in
  one process; decide whether the in-process `AsyncActionCallbacks` path stays (then a
  shared translation kernel is needed) or the worker becomes the only runner.
- Future option (discussed 2026-11-23, not needed now): per-tool sessions. Replace the
  shared `MemAgentDeps.db` with a session factory; `tool_transaction` opens one session
  per call. Removes shared-session hazards and would allow parallel tool calls, but needs
  write-race handling (read-modify-write on shadow rows, unique constraints), takes more
  connections, and touches all ~76 tools. Order between dependent calls in one response
  still needs sequential mode. Today each stage runs under
  `ToolManager.parallel_execution_mode("sequential")` with one shared session.
- Future options for publication cost, only if profiling still shows it after the async move:
  cache `_operations` SQL rendered once with sentinel UUIDs (~6.5 ms per publish), or a
  `publish_workspace(uuid, uuid)` plpgsql function (one round trip, shorter lock hold; per-table
  SQL then lives in a migration).
- Rejected: `asyncio.run` from sync code into async functions (needs a new
  session and transaction, breaks pooled async connections across loops, fails
  inside a running loop); sync duplicates of shared readers.
- Method that worked: a mechanical conversion pass, then Pyrefly to find every
  remaining sync caller (`unused-coroutine`, attribute access on `Coroutine`).
- Test pitfalls: async test engine needs `NullPool` (TestClient runs its own
  loop); a test that expires its sync session after a route deleted a row
  through the async session must read ids before `expire_all()`.
- Benchmarks (dev data): Argon2 hash/verify about 50 ms each (only CPU work over
  the 10 ms threshold); whole-novel upload parse 34 ms; term search and label
  span checks well under 15 ms.

## 2. Autolabel promotion as a background job (backend merged in #144; frontend in progress)

Measured on a real 381-chapter run copied to the test DB: about 5 ms per
chapter, about 10 s for 1,900 chapters in one request, event-loop stalls up to
about 1 s; no regression from the async/psycopg 3 change versus `master`.

Done: promotion code, its schemas, and its endpoint moved from
`labels` to `src/autolabels/promotions/processing.py` (pure move; OpenAPI unchanged), so
`labels` no longer imports `autolabels`. Model and migration
`4ea4c662b46f`: `label_promotion_jobs` (run, group, requester, requested filter,
status, message, claim token and lease; partial unique index on one active job
per run and group) and `label_promotion_job_items` (`(promotion_id,
auto_label_id)`, position, outcome, message), membership fixed at creation.

Agreed next:
- `POST` creates the job and all items in one `INSERT ... SELECT` from the
  candidate query (permission and filters applied once; chapters already holding
  label data in the group excluded) and returns the job. A repeat while a job is
  active returns it; if its lease expired, re-enqueue it.
- `GET /novels/{novelId}/label-promotions`: jobs joined to the novel's label
  groups under label-group read permission, ordered
  `(status IN ('pending','processing')) DESC, updated_at DESC`, limit about 10;
  counts and failures aggregated from items. No single-job GET.
- A new taskiq jobs worker (plain backend image, no ML dependencies, runs by
  default) rather than the manual-profile ML autolabels worker; behind a thin
  dispatcher protocol with `aenqueue(promotion_id)` and a recording test double.
- Worker: claim with token and lease, process `outcome IS NULL ORDER BY
  position` in batches, commit each batch's labels and item outcomes together,
  extend the lease per batch. An item whose autolabel content version is no
  longer the chapter's latest fails as "chapter changed".
- Later, consider moving run listing and creation out of the controller too,
  keeping the preview there.
- Before deployment, add a sweeper that redispatches stale pending promotions
  and jobs with expired claims. Recovery uses the original job ID and works
  after the client disconnects. Keep the active-job conflict on repeat POSTs.
  Cover a failed initial enqueue followed by one sweep, plus duplicate delivery
  with a single set of persisted labels.
- Later, after the promotion UI (user request, 2026-11-22): eager promotion.
  Today only chapters without label data in the group are filled; chapters that
  already have one fail with "already has label data". Wanted: insert into
  existing label datas, skipping (user toggle, on by default) only label datas
  with at least one label. A `mode` column on `label_promotion_jobs` would carry
  it; only the insert statement's choice of label datas and spans changes.
- Frontend polling (done on branch `feature/label-promotion-polling`, not yet a
  PR): `GET .../label-promotions?promotionIds=` (max `MAX_POLLED_PROMOTIONS` =
  10, `limit` still applies). `frontend/src/autolabels/promotions/` holds the
  pure reducers, `usePromotionJobs` and the prop-only `PromotionJobsList`; new
  autolabel code goes under `src/autolabels/`, existing code moves there
  gradually as it stops needing the controller. `AutoLabelPanel` owns the hook
  (the tab is `keepMounted`; polling does not pause on hidden tabs). The hook's
  effect is a single consumer loop: producers set `pending` (a reseed beats a
  poll) and call `notify`, so only one read is ever in flight. On finish,
  `labelGroupMgr.reloadPromotedLabelGroup` reloads the group in loaded chapters,
  open chapter first. Accepted: edits attempted during a reload are rejected (a
  reload waits for in-flight edits via ID-repo reservations); jobs started
  elsewhere appear only on mount, a 409 or `refresh`. Removed: the workspace
  lock, the controller promotion path, and the synchronous
  `POST /label-groups/{id}/label-datas/auto-labels` route.
- Follow-up: test fixtures (`tests/fixtures/scenarios.py`) and three
  integration tests still seed through `insert_label_datas_by_autolabels`; move
  them to the job path, then delete it and `CreateLabelDataByAutoLabelStatus`.
  Small open choice: count in-flight POSTs in `queue`'s cap check.

## 3. Label permission refactor

Label helpers in `src/labels/permissions.py` decide from the novel role only
(read: can see the novel; write: novel owner or editor). Also change label group
creation (stops inserting a `LabelContributor` owner), "my label groups", and
the workflow check in `src/filters/permissions.py`. Then remove the label
contributor endpoint, schema, `LabelRole`, and table in a follow-up. No frontend
UI uses label contributors.

## 4. Bulk chapter publish

Range endpoint (`POST /novels/{novelId}/chapters/visibility` with a chapter-number
range and `is_public`, one permission-wrapped update) and editor UI. Today only
single-chapter publish exists.

## 5-6. Small frontend items

Remove the frontend view pages (`frontend/src/view/`); show the novel title on
the edit page.

## 7. Autolabels UI refactor

The autolabels UI dates from early frontend work; see item 2 for the controller
split.

## 8-9. Reader feedback and mascot

Feedback endpoint and unintrusive reader UI (mobile and desktop); a mascot.
Open questions: anonymous submission and rate limiting (the reader has no
login), anchoring to a chapter content version with character offsets,
progressive enhancement (the reader works without JavaScript), and export to
the analytics store as a `reader_feedback.v1` kind.

## Smaller follow-ups

- Bulk chapter upload: defer the import to the jobs worker; until then the parse
  runs in `asyncio.to_thread`. Return 422 via `RequestValidationError` with
  `e.errors(include_input=False, include_url=False)` instead of echoing the
  uploaded body.
- PR #142 (reader images, Compose pulls `noveltl-reader-dev`) and PR #143 (CJK
  search e2e flake): for #143, consider `if: ${{ !cancelled() }}` so traces from
  flakes that pass on retry are uploaded.
- E2E and backend pytest both use `test_db`, and the e2e seed drops all tables;
  never run them at the same time.
