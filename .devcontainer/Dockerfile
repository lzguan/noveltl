FROM mcr.microsoft.com/devcontainers/javascript-node:dev-22-trixie

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
ENV npm_config_store_dir=/pnpm/store

ARG PROJECT_ROOT=/workspaces/NovelTL_Dev

# uv
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
RUN npm install --global corepack@latest --force
RUN corepack enable pnpm



RUN apt-get update && apt-get install -y postgresql-common && \
    yes | /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh && \
    apt-get install -y postgresql-client-18 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${PROJECT_ROOT}
COPY backend/pyproject.toml backend/uv.lock* ./backend/

RUN chown node:node ./backend -R
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/
RUN chown node:node ./frontend -R
COPY e2e/package.json e2e/pnpm-lock.yaml e2e/playwright.config.ts ./e2e/
RUN chown node:node ./e2e -R
RUN mkdir -p /home/node/.cache && chown node:node /home/node/.cache -R
RUN mkdir -p /home/node/.pnpm-store && chown node:node /home/node/.pnpm-store
RUN mkdir -p /pnpm && chown node:node /pnpm -R
RUN mkdir -p /home/node/.config/gh && chown node:node /home/node/.config/gh -R
RUN chown node:node ${PROJECT_ROOT} -R
RUN mkdir -p /home/node/.local && chown node:node /home/node/.local -R
RUN mkdir -p ${PROJECT_ROOT}/frontend/node_modules && chown node:node ${PROJECT_ROOT}/frontend/node_modules -R
RUN mkdir -p ${PROJECT_ROOT}/e2e/node_modules && chown node:node ${PROJECT_ROOT}/e2e/node_modules -R

USER node

WORKDIR ${PROJECT_ROOT}/backend
RUN --mount=type=cache,target=/home/node/.cache/uv,uid=1000,gid=1000 uv sync --all-groups --no-install-project
# pnpm
WORKDIR ${PROJECT_ROOT}/frontend
RUN --mount=type=cache,id=pnpm,target=/home/node/.pnpm-store,uid=1000,gid=1000 pnpm install
WORKDIR ${PROJECT_ROOT}/e2e
RUN --mount=type=cache,id=pnpm,target=/home/node/.pnpm-store,uid=1000,gid=1000 pnpm install
RUN pnpm ls
RUN --mount=type=cache,id=pnpm,target=/home/node/.pnpm-store,uid=1000,gid=1000 pnpm exec playwright install --with-deps
WORKDIR ${PROJECT_ROOT}
