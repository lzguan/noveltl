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

Remaining: `filters`, `autolabels`, then `memory` and `translations` together
with the Celery-to-taskiq move.

- Open decision for `filters`: its job state machine (`src/filters/lifecycle.py`)
  is shared by the HTTP service and the Celery runners. Proposed: keep it sync
  and call it from async code with `await db.run_sync(...)` (same connection and
  transaction) until the workers move; use `dispatcher.aenqueue`.
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
- Frontend: a hook polls the novel's list, and when a job it saw active
  finishes, reloads the target label group in every open chapter (new
  `novelDataManager` operation looping `chaptersIndex` and calling
  `reloadGroup`); keep the workspace lock for now. Later, consider moving run
  listing and creation out of the controller too, keeping the preview there.
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
- Frontend polling (agreed 2026-11-22, branch `feature/label-promotion-polling`):
  `GET .../label-promotions?promotionIds=` (max `MAX_POLLED_PROMOTIONS` = 10,
  `limit` still applies). A `usePromotionJobs` hook mounted in `EditNovelPage`
  owns `active` (by `createdAt`) and `finished` (by `updatedAt` desc, evict tail)
  lists, POSTs and polls the active snapshot about every 2 s; a re-seed
  generation guards against racing polls. On finish it reloads the group in
  loaded chapters, active chapter first, via a helper emitting `loadLabelData`.
  Accepted: edits attempted during a reload are rejected; a reload is serialized
  after in-flight edits by ID-repo reservations. The workspace lock and the
  controller promotion path are removed; `PromotionJobsList` stays prop-only
  because `AutoLabelRunsPanel` will be refactored.

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
