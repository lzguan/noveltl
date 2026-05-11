FROM mcr.microsoft.com/devcontainers/javascript-node:dev-22-trixie

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
ENV npm_config_store_dir=/pnpm/store

WORKDIR /project-deps
# uv
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
RUN npm install --global corepack@latest --force
RUN corepack enable pnpm

ENV UV_PROJECT_ENVIRONMENT="/.venv"


RUN mkdir -p /.venv && chown node:node /.venv
RUN apt-get update && apt-get install -y postgresql-common && \
    yes | /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh && \
    apt-get install -y postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/uv.lock* ./backend/

RUN chown node:node ./backend/pyproject.toml ./backend/uv.lock
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN chown node:node ./package.json ./pnpm-lock.yaml ./pnpm-workspace.yaml
RUN mkdir -p /home/node/.cache && chown node:node /home/node/.cache -R
RUN mkdir -p /home/node/.pnpm-store && chown node:node /home/node/.pnpm-store
RUN mkdir -p /pnpm && chown node:node /pnpm -R
RUN chown node:node /project-deps -R
RUN mkdir -p /home/node/.local && chown node:node /home/node/.local -R


USER node

WORKDIR /project-deps/backend
RUN --mount=type=cache,target=/home/node/.cache/uv,uid=1000,gid=1000 uv sync --all-groups --no-install-project
# pnpm
WORKDIR /project-deps/frontend
RUN --mount=type=cache,id=pnpm,target=/home/node/.pnpm-store,uid=1000,gid=1000 pnpm install
WORKDIR /project-deps
