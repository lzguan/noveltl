# Verification entry points

Follow the root [AGENTS.md](../../AGENTS.md) for execution constraints and
[docs/scripts.md](../../docs/scripts.md) for the maintained command reference.
Use the [test-writing skill](../skills/test-writing/SKILL.md) when selecting,
writing, or changing regression coverage.

## Scope

The [memory-job](memory-jobs.md) and [term-translation](term-translations.md) notes
link to focused tests. Backend database behavior needs the real PostgreSQL
fixtures. Task tests replace paid inference with Pydantic AI test/function models;
passing them does not establish naming quality.

The session-scoped `database_schema` fixture in
[conftest.py](../../backend/tests/conftest.py) builds the schema once; each
`test_db` setup truncates every `Base.metadata` table with `RESTART IDENTITY`
instead of rebuilding. Tests that need their own DDL (migration tests, shadow
schema) create and drop an isolated schema rather than touching `public`. A new
test that alters `public` tables must restore them or use the same pattern. The
`test_db` Compose service keeps its data on tmpfs with `fsync`,
`synchronous_commit`, and `full_page_writes` off, so it is lost on restart.

Backend changes should run relevant tests and lint/type checks. Pure file moves
or import changes can use static checks and a runtime import check. Documentation
changes need link/path checks and `git diff --check`.

## API generation

After a public schema change, run both steps from the repository root:

```bash
uv --directory backend run --no-sync python -m scripts.extract_openapi
pnpm --dir frontend generate:api
```

Review OpenAPI and generated client changes together. The frontend generator
temporarily removes generated directories before rebuilding them; wait for it
to finish before interpreting the diff or running dependent checks. Do not edit
generated files manually.

Internal config/context changes do not inherently change OpenAPI. Check the
actual schema before regenerating clients for such a change.

For frontend behavior changes, use the
[frontend-conventions skill](../skills/frontend-conventions/SKILL.md). Commands
are listed in [frontend/package.json](../../frontend/package.json).

Frontend tests default to jsdom. Files that never render or touch browser APIs
start with `// @vitest-environment node` to skip jsdom setup; `setupTests.ts`
only installs jsdom storage when jsdom exists. Component tests mount the
narrowest owner (e.g. `GlossaryBrowser`, `MemoryBrowser`) rather than the whole
`MemoryPanel`. On the 4-CPU devcontainer, near-5s tests can time out under load;
check before re-running the suite.

## Known e2e flake

`search navigation selects a rare CJK term in a newly loaded chapter`
([editor-unicode-offsets.spec.ts](../../e2e/tests/editor-unicode-offsets.spec.ts))
failed in CI on 2026-11-15 (typed `X` landed at offset 0, so the 𠮷 selection
was lost) and again on 2026-11-22 (same wrong editor text); both passed on
rerun. The app is unchanged; only the test was hardened.

- Spec hardening: `chapterNumber(base, testInfo)` offsets every chapter in the
  spec by 10 per attempt (`repeatEachIndex`, `retry`), so retries and
  `--repeat-each` no longer hit "chapter already exists" (the seed resets the DB
  only once per run). The CJK test now asserts, with distinct messages, that a
  `.cm-selectionBackground` exists after clicking the occurrence ("did not
  select") and that the DOM selection is `𠮷` after Edit and focus ("lost
  before typing"). A failure past both points to typing/input, not selection.
- Unproven app races that would drop the selection on a slow machine:
  `switchChapter` returns early when the tab is already `loading`, discarding the
  highlight ([chapterManager.ts](../../frontend/src/edit/managers/chapterManager.ts));
  the cached open path keeps the highlight only when `isTextSynced()`
  ([novelDataManager.ts](../../frontend/src/edit/controller/novelDataManager.ts)).
  Neither has been reproduced; the next CI failure's message and trace should
  say which stage drops it.
- CI runs e2e against its own Postgres service (`.github/workflows/test-e2e.yml`),
  not the Compose `test_db`. The config keeps traces for failed and retried
  attempts (`retain-on-failure-and-retries`), and the workflow uploads
  `playwright-report/` and `test-results/` only when the job fails, so a flake
  that passes on retry leaves no artifact.
- Local runs: the spec runs against Compose `test_db`/`test_redis` once the
  worktree has `backend/.venv` and `frontend/node_modules`; the seed drops all
  tables, so do not overlap it with backend pytest.
