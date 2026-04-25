# AGENTS.md

## Project

NovelTL is a collaborative novel-translation platform. It combines manual labeling workflows with NER-assisted auto-labeling to keep names and terminology consistent across long texts.

Stack:
- Frontend: React 19, TypeScript 7, Vite, pnpm
- Backend: FastAPI, SQLAlchemy, Alembic
- Infra: PostgreSQL, Redis, ARQ worker

## Repo Layout

- `backend/`: API, migrations, scripts, tests
- `frontend/`: app, API client layer, components, tests
- `docs/`: current technical docs
- `compose.yaml`: local multi-service setup

## Commands

Frontend, from `frontend/`:
- `pnpm dev`
- `pnpm build`
- `pnpm lint`
- `pnpm test`
- `pnpm exec vitest run`
- `pnpm exec tsgo -p tsconfig.app.json --noEmit`

Backend, from repo root after `source /.venv/bin/activate`:
- `pytest backend/`
- `pytest backend/tests/auth/test_auth.py`
- `pytest backend/ -m "slow or not slow"`
- `ruff format .`
- `ruff check --fix .`
- `cd backend && pyrefly check`

Database, from `backend/`:
- `alembic upgrade head`
- `alembic revision --autogenerate -m "..."`
- `alembic downgrade -1`

## Conventions

Backend:
- Service functions: `query_*`, `insert_*`, `modify_*`, `remove_*`
- Router functions: `read_*`, `create_*`, `update_*`, `delete_*`, `action_*`
- Permissions are enforced at the SQL layer, usually in `permissions.py`

Frontend:
- Components/pages: `PascalCase.tsx`
- Utilities/API modules: `camelCase.ts`
- Named exports only
- Pages live in `frontend/src/pages/`
- Use `pnpm` for frontend package/scripts and `tsgo` instead of `tsc` for TypeScript checks

API boundary:
- Backend uses `snake_case`
- Frontend uses `camelCase`
- Mapping is manual in `frontend/src/api/*.ts`

Testing:
- Frontend API tests live in `frontend/src/api/__test__/`
- They mock `src/api/client.ts`
- Prefer `satisfies` and `expectTypeOf`

## Current Caveat

The repo currently has mixed terminology for chapter text versioning:
- Frontend and several docs use `revision` / `revision_text`
- Current backend router uses `chapter` / `chapter_content`

Do not assume those are fully reconciled. Check code and docs before changing related flows.

## Docs To Prefer

Start with:
- `docs/README.md`
- `docs/architecture.md`
- `docs/database-schema.md`
- `docs/conventions.md`
- `docs/permissions.md`

Feature docs:
- `docs/background-jobs.md`
- `docs/filter-system.md`
- `docs/editable-with-labels.md`
- `docs/sourcework-model.md`
- `docs/workspace-implementation.md`
