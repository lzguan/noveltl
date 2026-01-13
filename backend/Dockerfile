FROM python:3.12-slim AS base
WORKDIR /project
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./
ENV UV_PROJECT_ENVIRONMENT="/app"
RUN uv sync --frozen --no-default-groups --no-install-project
ENV PATH="/app/bin:$PATH"

FROM base AS backend
RUN uv sync --frozen --group backend
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0"]

FROM base AS worker
RUN uv sync --frozen --group worker
COPY . .
CMD ["arq", "src.autolabels.worker.worker.WorkerSettings"]