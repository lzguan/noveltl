Automated translation platform for Chinese webnovels. Contains a suite of tools to assist in translations:
- Automated text labeller
- Automated glossary builder
- Manual review tools to ensure labelling accuracy

## Getting started

Disclaimer: the author has not had time to check that these commands work yet. Please contact the author if any of these commands do not work.

1. Clone the repository.
2. Copy `.env.example` into `.env` and configure the indicated variables.
3. Run `docker compose up -d`.
4. To enable automated text labelling, run `docker compose up -d worker`.
5. Run `docker compose exec -it backend uv run alembic upgrade head`.
6. Run `docker compose exec -it backend uv run python -m scripts.seed_admin`.
7. In the same folder, run `docker compose exec -it backend uv run python -m scripts.seed_languages`.
8. Navigate to `localhost:5173` and log in.

Alternatively, 

1. Open the project in VSCode.
2. Copy `.env.example` into `.env` and configure the indicated variables.
3. Open the project in a devcontainer.
4. To enable automated text labelling, run `docker compose up -d worker` in the local shell.
5. In the devcontainer, navigate to `backend/` and run `uv run python -m scripts.seed_admin`. Enter a username/password.
6. In the same folder, run `uv run python -m scripts.seed_languages`.
7. Navigate to `localhost:5173` and log in.

## Coming eventually

- Better tooling for manual review
- One-click automated novel translation

## Tech stack

- FastAPI + SQLAlchemy + Pydantic for backend
- Pytest for backend tests
- PostgreSQL database + Alembic for migrations
- Redis for queueing jobs + request caching
- TypeScript + React for frontend
- Vite dev server + Vitest
- Backend tools: uv, ruff, Pyrefly
- Frontend tools: pnpm, ShadCN, hey-api

Nothing too fancy here. Read docs for details.

## Contributing

Please read the docs/code. Developing in devcontainer is recommended since everything is already configured. If you need assistance with installing coding agents in devcontainer, please see [coding agents](docs/coding-agents.md).