FROM python:3.12-slim AS base
WORKDIR /project
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-default-groups --no-install-project

FROM base AS backend
RUN uv sync --frozen --group backend --no-dev --no-install-project
COPY . .
CMD ["uv", "run", "--no-sync", "uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS worker
RUN uv sync --frozen --group worker --no-dev --no-install-project
COPY . .
CMD ["uv", "run", "--no-sync", "arq", "src.autolabels.worker.worker.WorkerSettings"]