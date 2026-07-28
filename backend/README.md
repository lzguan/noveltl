# NovelTL backend

The backend is a FastAPI application responsible for authentication, novels
and versioned chapter text, labels, autolabel jobs, editor synchronization, and
request caching. It stores persistent data in PostgreSQL and uses Redis for
background-job queueing and short-lived request state.

Start with the repository [documentation index](../docs/README.md) and
[project structure](../docs/project-structure.md). The domain introductions
for [novels](../docs/novels.md), [labels](../docs/labels.md),
[autolabels](../docs/autolabels.md), and the
[editor](../docs/editor/README.md) explain the main data flows.

## Structure

Most features live under `src/<service>/`. A service may contain:

- `router.py` for FastAPI routes;
- `service.py` for database-backed domain operations;
- `models.py` for SQLAlchemy models;
- `schemas.py` for Pydantic request and response models;
- `permissions.py` for query-level access control;
- `exceptions.py` and `dependencies.py` for HTTP integration.

[`src/main.py`](src/main.py) constructs the application and registers its
routers. [`src/models.py`](src/models.py) imports all SQLAlchemy model modules
so Alembic and test setup share one metadata registry.

The autolabel worker is a separate process under
[`src/autolabels/worker/`](src/autolabels/worker/). It consumes Arq jobs from
Redis and writes inference results to PostgreSQL.

## Development

The devcontainer is the supported development environment. It installs the
backend environment with `uv` and supplies the PostgreSQL and Redis connection
settings from Compose. See [onboarding](../docs/onboarding.md) for setup.

From the repository root:

```bash
uv --directory backend run uvicorn src.main:app --reload
uv --directory backend run ruff check
uv --directory backend run pyrefly check
uv --directory backend run pytest
```

The application requires configured database, Redis, and `SECRET_KEY`
environment values. The test suite additionally requires the Compose
`test_db` and `test_redis` services; it recreates the test database schema.

Create or update the database schema with Alembic:

```bash
uv --directory backend run alembic upgrade head
```

Seed a new development database:

```bash
uv --directory backend run python -m scripts.seed_languages
uv --directory backend run python -m scripts.seed_admin
```

See [scripts.md](../docs/scripts.md) for OpenAPI generation and test-data
utilities.

## API and migrations

The backend OpenAPI documents are committed as `openapi.json` and
`openapi.yaml`. The frontend client is generated from the YAML document; update
both artifacts whenever the public FastAPI schema changes.

Database model changes require an Alembic migration. Registering a model in
`src/models.py` makes it visible to SQLAlchemy, but does not update an existing
database by itself.

## Tests

Tests mirror the backend service layout under [`tests/`](tests/). Most
integration tests use a real PostgreSQL database because behavior such as
exclusion constraints and PostgreSQL JSON types cannot be represented
faithfully by SQLite. Redis queue behavior is exercised through the test Redis
service, while request-cache behavior uses in-memory fakes where appropriate.

Slow or model-heavy tests are excluded by the default pytest configuration.
