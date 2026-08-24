# Useful scripts

**Last updated:** 2026-07-28

Commands below are written for the repository root unless a different working
directory is specified.

## Database utilities

Open a PostgreSQL shell through the helper in `database/connection/`:

```bash
database/connection/connect_to_psql
```

Create a local database backup with the `pg_dump` wrapper:

```bash
bash database/db_backups/backup_db
```

The backup helper connects to the `db` service on the Compose network and
writes its output under `database/db_backups/`.

Apply all committed Alembic migrations:

```bash
uv --directory backend run alembic upgrade head
```

Seed supported languages and create an administrator:

```bash
uv --directory backend run python -m scripts.seed_languages
uv --directory backend run python -m scripts.seed_admin
```

The administrator script prompts for a username and password.

## Regenerate the frontend API client

Public FastAPI schema changes require two steps. First regenerate the committed
OpenAPI JSON and YAML documents:

```bash
uv --directory backend run --no-sync python -m scripts.extract_openapi
```

Then run Orval from the frontend project:

```bash
pnpm --dir frontend exec orval
```

Orval reads `frontend/orval.config.ts` and writes generated models and clients
under `frontend/src/api/`. Do not edit those generated files manually. Review
changes to the OpenAPI documents and generated client together.

## Checks and tests

Backend:

```bash
uv --directory backend run ruff check
uv --directory backend run pyrefly check
uv --directory backend run pytest
uv --directory backend run pytest -m integration
```

Frontend:

```bash
pnpm --dir frontend check
pnpm --dir frontend lint
pnpm --dir frontend format:check
pnpm --dir frontend test:ci
```

The default backend test selection excludes slow, live-agent, and external-service
integration tests. Run the integration selection separately to exercise Redis,
Celery workers, and other real service boundaries. The backend tests require the
configured test PostgreSQL and Redis services; the devcontainer receives their
connection settings from `compose.yaml`.

The Playwright project starts its own backend and frontend processes, but uses
the test database and Redis services:

```bash
docker compose --profile test up -d test_db test_redis
pnpm --dir e2e check
pnpm --dir e2e lint
pnpm --dir e2e test
```

Use `pnpm --dir e2e test:headed` or `pnpm --dir e2e test:ui` for interactive
browser debugging.

## Versioned test data

Run these commands from `backend/`, where `.venv/bin/python` is the interpreter
managed by uv:

```bash
.venv/bin/python -m scripts.add_test_novel INPUT_DIR DATASET_DIR
.venv/bin/python -m scripts.export_test_chapter_upload DATASET_DIR NOVEL_ID OUTPUT_FILE
.venv/bin/python -m scripts.generate_test_autolabels DATASET_DIR NOVEL_ID --config CONFIG_ID
.venv/bin/python -m scripts.generate_test_data_schema --version 1
.venv/bin/python -m scripts.lock_test_data DATASET_DIR --all --check
```

The export script additionally accepts `--format v1` and
`--content-version latest|N`. The authoring commands have further selector,
dry-run, and replacement options documented in the
[V1 test-data guide](../backend/tests/test_data/schema/v1/README.md).

General frontend scripts are defined in
[`frontend/package.json`](../frontend/package.json). Backend dependency groups
and tool configuration are defined in
[`backend/pyproject.toml`](../backend/pyproject.toml).
