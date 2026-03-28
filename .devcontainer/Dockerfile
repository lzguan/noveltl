FROM mcr.microsoft.com/devcontainers/python:3.12-trixie
WORKDIR /project
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT="/.venv"
RUN mkdir -p /.venv && chown vscode:vscode /.venv
RUN apt-get update && apt-get install -y postgresql-common && \
    yes | /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh && \
    apt-get install -y postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/uv.lock* ./
USER vscode
RUN --mount=type=cache,target=/root/.cache/uv\
    uv sync --all-groups --no-install-project