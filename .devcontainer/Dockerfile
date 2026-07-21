FROM mcr.microsoft.com/devcontainers/base:dev-trixie

ARG PNPM_VERSION=11.10.0
ARG NODE_VERSION=22
ARG PROJECT_ROOT=/workspaces/NovelTL_Dev

ENV PNPM_HOME=/home/vscode/.local/share/pnpm
ENV PATH="${PNPM_HOME}/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y libatomic1 postgresql-common \
    && yes | /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh \
    && apt-get install -y postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

USER vscode
COPY --from=ghcr.io/astral-sh/uv:0.10.9 --chown=vscode:vscode /uv /uvx /bin/
RUN wget -qO- https://get.pnpm.io/install.sh | ENV="$HOME/.bashrc" SHELL="/bin/bash" bash -
RUN pnpm runtime set node ${NODE_VERSION} -g

WORKDIR ${PROJECT_ROOT}
COPY --chown=vscode:vscode backend/pyproject.toml backend/uv.lock* ./backend/

COPY --chown=vscode:vscode frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/
COPY --chown=vscode:vscode e2e/package.json e2e/pnpm-lock.yaml e2e/playwright.config.ts ./e2e/

# populate uv/pnpm caches to speed up development container installation
WORKDIR ${PROJECT_ROOT}/backend
RUN uv sync --all-groups --no-install-project && rm -rf .venv
WORKDIR ${PROJECT_ROOT}/frontend
RUN pnpm fetch --frozen-lockfile
WORKDIR ${PROJECT_ROOT}/e2e
RUN pnpm install --frozen-lockfile \
    && pnpm exec playwright install --with-deps chromium \
    && rm -rf node_modules \
    && sudo rm -rf /var/lib/apt/lists/*
WORKDIR ${PROJECT_ROOT}
