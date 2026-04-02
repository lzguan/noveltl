# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

NovelTL is a collaborative web platform for novel translation. LLMs struggle with consistency over long novels (character names, locations drift). NovelTL runs Named Entity Recognition (NER) on chapter content, lets users review/verify those labels, and generates glossaries for use in translation workflows.

## Development Environment

The project runs in Docker Compose. The devcontainer uses `compose.yaml` + `.devcontainer/docker-compose.yml` and starts the `dev`, `db`, `redis`, and `worker` services. The GitHub CLI (`gh`) is pre-installed and auth is mounted from the host.

```bash
source /.venv/bin/activate          # Activate backend venv (always do this first)
cd backend && alembic upgrade head  # Apply DB migrations
python scripts/seed_admin.py        # Create admin user
python scripts/seed_languages.py    # Seed language codes
```

### Branch Protection

The `master` branch is protected. All changes must go through a pull request with at least one approval — never push directly to `master`. Use `gh pr create` to open PRs.

## Commands

### Frontend (run from `frontend/`)
```bash
npm run dev          # Start Vite dev server
npm run build        # Production build
npm run lint         # ESLint
npm run test         # Run Vitest (watch mode)
npx vitest run       # Single test run
npx vitest run src/api/__test__/novels.test.ts  # Run one test file
npx tsc -p tsconfig.app.json --noEmit           # Type check (includes test files)
```

### Backend (run from project root)

> **Note:** The devcontainer does not have the `docker` CLI. Activate the backend venv first — this puts `pytest`, `ruff`, `pyright`, `alembic`, etc. on PATH and ensures DB/Redis connections work.

```bash
source /.venv/bin/activate                                      # Activate backend venv (do this first)
pytest backend/                                                 # All tests (slow tests excluded by default)
pytest backend/tests/auth/test_auth.py                          # Single test file
pytest backend/tests/auth/test_auth.py::test_fn                 # Single test
pytest backend/ -m "slow or not slow"                           # Include slow tests
ruff format .                                                   # Format
ruff check --fix .                                              # Lint + auto-fix
pyright                                                         # Type check (strict mode)
```

### Database (run from `backend/`)
```bash
alembic upgrade head                      # Apply migrations
alembic revision --autogenerate -m "..."  # New migration
alembic downgrade -1                      # Rollback one
```

## Architecture

```
React Frontend (Vite, port 5173)
        ↓ REST + JWT
FastAPI Backend (port 8000)
  ├── auth/        — JWT login/registration, Argon2 hashing
  ├── novels/      — novels, chapters, immutable revisions, contributor roles
  ├── labels/      — entity annotations, label groups/data, overlap detection
  ├── autolabels/  — background NER via Redis/ARQ (PENDING→PROCESSING→DONE/FAILED)
  ├── filters/     — 4-phase label pipeline (score filtering, extensible)
  └── languages/   — ISO 639-1 codes, read-only, no auth required
        ↓
PostgreSQL + Redis (ARQ task queue for NER worker)
```

Each backend service follows the same layout: `router.py`, `service.py`, `models.py`, `schemas.py`, `permissions.py`.

## Key Architectural Patterns

### Permissions (Backend)
Permissions are enforced at the SQL level, not application level. Every service has a `permissions.py` with helpers named `{resource}_mod_access_{operation}` (e.g., `novel_mod_access_select`). These helpers take a SQLAlchemy `Select` statement and add `WHERE` clauses based on the current user:
- **Admin** → no WHERE clause added (full bypass)
- **Guest (None)** → filter to `visibility >= UNLISTED`
- **Regular user** → public/unlisted OR user is a contributor

For inserts that depend on parent permissions, the pattern is an atomic `INSERT ... SELECT` — the SELECT applies permission WHERE clauses, and if denied, the insert returns no rows (raises `NoResultFound`).

### Case Conversion Boundary (Frontend)
The backend uses `snake_case`; the frontend uses `camelCase`. **Conversion is done manually in `frontend/src/api/*.ts`** — there is no automatic transformation middleware. Each API function maps `response.data.snake_key` → `camelKey` on the way out and `camelKey` → `snake_key` on the way in.

### Immutable Revisions
Chapter content is never edited in-place. New `Revision` records are created; old ones are immutable. This applies to label data as well.

### Frontend API Tests
Tests live in `frontend/src/api/__test__/`. They mock `src/api/client.ts` at the module level and verify:
1. Correct HTTP method, URL, and request body shape (including snake_case keys)
2. Correct response mapping to camelCase TypeScript types
3. Use `satisfies` for runtime type checking and `expectTypeOf` for compile-time checking

See `docs/frontend-testing.md` for the full testing standard.

## Naming Conventions

### Backend
- Service functions: `query_*`, `insert_*`, `modify_*`, `remove_*`
- Router functions: `read_*`, `create_*`, `update_*`, `delete_*`, `action_*`
- URL path segments: `kebab-case`; path params: `snake_case`; query params: `kebab-case` with `alias=`
- DB FK columns: `{parent_singular}_id`; relationships: parent→`{children}_with_{parent}`, child→`{parent}_of_{child}`

### Frontend
- Components: `PascalCase.tsx`; utilities/API: `camelCase.ts`
- Named exports only — no default exports
- Pages named `{Feature}Page.tsx` and placed in `src/pages/`

## GitHub Issues

Issues are the source of truth for planned work, bugs, and suggestions. When you have a suggestion or notice something worth improving during development, create a GitHub issue for it rather than implementing it immediately. After merging any PR, check open issues and close any that were resolved by the changes.

## Key Documentation
- `docs/conventions.md` — full naming conventions (backend + frontend)
- `docs/architecture.md` — service design, communication patterns
- `docs/permissions.md` — visibility levels, contributor roles, access control
- `docs/frontend-testing.md` — frontend API test standards
- `docs/filter-system.md` — 4-phase filter pipeline design
- `docs/background-jobs.md` — AutoLabel worker, state machine, concurrency
