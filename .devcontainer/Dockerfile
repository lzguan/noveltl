FROM mcr.microsoft.com/devcontainers/python:3.12-trixie
WORKDIR /project
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT="/app"
RUN mkdir -p /app && chown vscode:vscode /app
COPY backend/pyproject.toml backend/uv.lock* ./
USER vscode
RUN --mount=type=cache,target=/root/.cache/uv\
    uv sync --all-groups --no-install-project