# Backend Testing Guide

**Last Updated**: March 8, 2026  
**Status**: Complete

This document describes the testing architecture, key design decisions, and non-obvious patterns. For code details, see the source files directly — they are the authoritative reference.

---

## Table of Contents

1. [Architecture Decisions](#architecture-decisions)
2. [Test Organization](#test-organization)
3. [Running Tests](#running-tests)
4. [Key Patterns](#key-patterns)

---

## Architecture Decisions

### Full database reset per test

Every test function gets a fresh database: `test_db` drops all tables, enables `btree_gist` (required for exclusion constraints), and recreates the schema from SQLAlchemy models. This is slow but guarantees total isolation — no test can be affected by another's side effects.

### Dependency injection via FastAPI overrides

The `client` fixture overrides `get_db` and `get_redis_for_app` so all API calls route through the test database and test Redis (database index 1, not production 0). Overrides are cleared after each test.

### Monkeypatching for worker isolation

The ARQ worker creates its own `SessionLocal` independently of FastAPI's dependency injection. The `worker_mock` fixture uses `monkeypatch.setattr` to replace the `SessionLocal` reference **in the worker's module namespace** (not the original definition), pointing it at the test database. The worker runs with `burst=True` and `poll_delay=0` so it processes all queued tasks immediately and exits. See [concepts/monkeypatching.md](concepts/monkeypatching.md) for a detailed explanation of why this works.

### Password hashing fixtures

`password_hash.py` provides two fixtures: `recommended_hash` (real argon2 via pwdlib) and `no_hash` (identity function, for tests where hashing speed matters). Both conform to a `Hash` protocol so they're interchangeable. Population fixtures use `recommended_hash` by default.

### Async test mode

`asyncio_mode = "auto"` in pyproject.toml — no need for `@pytest.mark.asyncio` on every async test. `asyncio_default_fixture_loop_scope = "function"` ensures each test gets its own event loop.

## Test Organization

Tests are organized by service, mirroring `backend/src/`:

```
backend/tests/
├── conftest.py          # Core fixtures: test_db, client, redis, worker_mock, DataLoader
├── fixtures/
│   ├── populators/      # One file per test scenario (sample, permissions, filters, etc.)
│   ├── password_hash.py # Hash/NoHash fixtures
│   └── filters.py       # Filter object fixtures (e.g., ScoreFilter instance)
├── auth/                # Auth service tests
├── autolabels/          # AutoLabel tests
│   └── worker/          # Worker unit tests (chunking, tokenizer)
├── filters/             # Filter pipeline tests
├── labels/              # Label CRUD + permissions tests
├── languages/           # Language service tests
├── novels/              # Novel CRUD + permissions tests
├── demos/               # Learning examples (monkeypatching demos)
└── test_data/           # Sample chapter text and autolabel JSON files
```

### Fixture registration

All fixture files are registered via `pytest_plugins` in `conftest.py` — not auto-discovered. Adding a new populator file requires adding it to the list.

### Population fixtures

Each file in `fixtures/populators/` creates a specific data scenario by composing granular fixtures (e.g., `sample_languages` → `sample_users` → `sample_novels` → `sample_chapters`). Fixtures use the actual model field names (`user_name`, `user_hashed_password`, etc.) and return dicts for named access. To keep test data separate from code, fixture definitions use the `DataLoader` fixture, described below.

### DataLoader

`conftest.py` provides `chapter_loader` and `autolabel_loader` fixtures — `DataLoader` instances that read files from `test_data/` by subdirectory and glob pattern. Call with `loader("subdir")` for flat listing or `loader("subdir", recursive=True)` for recursive. Returns a generator of file contents sorted by filename.

## Running Tests

All `pytest` commands must be run from the **`backend/`** directory (where `pyproject.toml` is located):

```bash
cd backend/
pytest                          # Runs all non-slow tests (default via addopts)
pytest -m slow                  # Only slow tests (worker integration)
pytest -m implementation        # Only implementation tests
pytest tests/filters/           # Specific service
```

Default behavior from pyproject.toml: `-ra -q -m 'not slow'` — shows summary of failures, quiet output, skips slow-marked tests.

### Coverage

`coverage` is installed. Wrap pytest with `coverage run` to collect data, then use `coverage report` or `coverage html` to view results:

```bash
coverage run -m pytest                              # Collect coverage for full test run
coverage run --source=src -m pytest                  # Restrict to src/ only
coverage run --source=src/novels -m pytest tests/novels/  # Single service
coverage report -m                                   # Terminal report with missing lines
coverage html                                        # HTML report in htmlcov/
```

The HTML report (`htmlcov/index.html`) is useful for exploring uncovered branches visually. Combine pytest flags as usual (e.g., `coverage run -m pytest -m "not slow"`).

### Markers

- **`slow`** — Worker integration tests that enqueue + run ARQ tasks. Skipped by default.
- **`implementation`** — Heavy model tests (e.g., NER inference with real models).

## Key Patterns

### Router / endpoint tests

Test the HTTP layer via `TestClient`. Sync.

1. Populate data via a fixture
2. Authenticate via `client.post("/token", ...)`
3. Call the endpoint
4. Assert status code + response body

*Examples: auth endpoint tests, languages endpoint tests.*

### Service-layer tests

Test business logic by calling service functions directly against `test_db`. Sync. This is the bulk of the test suite — covers CRUD operations, permission-filtered queries, and data integrity.

*Examples: `query_novels_by_title` with different user visibility, `insert_label_datas_by_autolabels` verifying counts and data creation.*

### Permission / access-control tests

A specific category of service tests that exercise the query-modification permission helpers (`label_group_mod_access_select`, `label_data_mod_access_select`, `label_mod_access_delete`, etc.) with different user roles (owner, editor, viewer, non-member). These verify that the same query returns different results depending on who's asking.

*Examples: owner can `copy_label_group`, viewer cannot; editor can update, non-member gets nothing from select.*

### Worker integration tests

Test the full ARQ pipeline: enqueue via API → run worker → verify DB state. Async, marked `@pytest.mark.slow`.

1. Populate data + enqueue job via API
2. `await worker_mock.async_run()` (burst mode processes all tasks then exits)
3. `test_db.refresh(obj)` to pick up changes the worker committed
4. Assert state transitions (PENDING → DONE)

### Filter tests

Test each pipeline phase independently (flag → context → decide → apply). The `score_filter` fixture (from `fixtures/filters.py`) provides a `ScoreFilter()` instance; populator fixtures provide the test data. Two variants exist:
- **Synthetic data** (`score_filter_simple`) — small hand-crafted labels, fast
- **Real data** (`chinese_xianxia_small_test`) — 279 labels from actual Chinese text, tests completeness/preservation/deletion invariants

### Pure unit tests (no DB)

Test logic that doesn't need a database — currently only the autolabel worker's chunking utilities (`_chunk_blocks`, `_chunk_paragraph`, `chunk_text`). These create mock `Tokenizer` classes inline and test edge cases (empty text, oversized chunks, missing tokens).

### ML model tests

Test real NER model inference (`Cluener.predict()`) on actual chapter text. Marked `@pytest.mark.implementation` + `@pytest.mark.slow`. The `cluener` fixture is **session-scoped** (model loads once for all tests in the module).

### Database constraint tests

Test that SQLAlchemy model constraints work at the DB level (unique constraints, length limits) by asserting `IntegrityError`/`DataError` on violation. Currently only for languages.

### Test ordering / cross-test dependencies

Two tests use `pytest-dependency` and `pytest-order`: `test_labels_service.py` declares a named dependency (`insert_label_datas_by_autolabels`) that `test_score_filter_chinese_xianxia_small.py` depends on. This means label insertion must succeed before filter tests run against that data. This is the only ordered dependency chain.

## Relevant Files

- `backend/tests/conftest.py` — Core fixtures and DataLoader
- `backend/tests/fixtures/` — Population fixtures and filter fixtures
- `backend/pyproject.toml` — Pytest configuration (`[tool.pytest.ini_options]`)
- `backend/tests/demos/monkeypatching/` — Monkeypatching learning examples

## See Also

- [testing-architecture.md](testing-architecture.md) — Test layer structure, dependency gates, fixture bundles
- [concepts/monkeypatching.md](concepts/monkeypatching.md) — Worker testing deep dive
- [background-jobs.md](background-jobs.md) — AutoLabel worker system
- [conventions.md](conventions.md) — Code conventions
- [architecture.md](architecture.md) — System architecture
