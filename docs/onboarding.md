# Onboarding

**Last updated:** 2026-07-20

## Getting started

Clone the project from Github. After that, setup the project using one of the methods below.

## Devcontainer setup

Devcontainers are a useful feature in VSCode that allow you to develop in a Docker container. 

To get started with devcontainers, open the project in VSCode and install the [Dev Containers](vscode:extension/ms-vscode-remote.remote-containers) extension. A popup should come up in the bottom right corner asking to reopen the current folder in a container. Alternatively, open the [Command Palette](https://code.visualstudio.com/docs/getstarted/userinterface#_command-palette) and select "Open Folder in Container" (or something like that). Wait for the container to finish building and you are all set.

Devcontainer configurations are found in [`../devcontainer`](../.devcontainer/). The devcontainer is configured to save Github CLI configs and agent conversations as volumes and load them on devcontainer creation for convenience. Currently this is supported for Claude Code and Codex. All tools mentioned [here](project-structure.md#toolstechnologies) are configured in the devcontainer. Coding agents must be installed separately.

> Note for Windows users: make sure to clone this repository onto the WSL filesystem and not the mounted Windows filesystem. 

## Local

Local setup not yet documented, we recommend using devcontainers for now.

## Local production-stack testing

Use [`compose.prod.yaml`](../compose.prod.yaml) to build and run the production container targets locally. This stack is separate from the development stack: it serves the built frontend through Caddy, does not bind-mount source code, and stores its PostgreSQL, Redis, and Caddy data in named volumes.

Create a local environment file from the tracked template:

```bash
cp .env.prod.example .env.prod.local
```

Generate separate values for `DB_PASSWORD` and `SECRET_KEY`, then place them in `.env.prod.local`:

```bash
openssl rand -hex 32
```

Leave `SITE_ADDRESS=:80` for local HTTP testing. The template's `COMPOSE_PROJECT_NAME=noveltl_prod_local` keeps this stack's containers, network, and volumes separate from the development stack.

Build the service images, then start PostgreSQL and Redis:

```bash
docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  build

docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  up -d db redis
```

The worker image downloads the pinned autolabel model during its first build, so the initial build may take longer than subsequent builds.

Run database migrations:

```bash
docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  run --rm backend uv run --no-sync alembic upgrade head
```

For a fresh database, seed the supported languages and create an administrator:

```bash
docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  run --rm backend uv run --no-sync python -m scripts.seed_languages

docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  run --rm backend uv run --no-sync python -m scripts.seed_admin
```

Start the complete stack:

```bash
docker compose \
  --env-file .env.prod.local \
  -f compose.prod.yaml \
  up -d
```

Open [http://localhost](http://localhost). View service status and logs with:

```bash
docker compose --env-file .env.prod.local -f compose.prod.yaml ps
docker compose --env-file .env.prod.local -f compose.prod.yaml logs -f
```

Stop the stack while preserving its named volumes:

```bash
docker compose --env-file .env.prod.local -f compose.prod.yaml down
```

Add `--volumes` only when intentionally deleting the local production database, Redis state, and Caddy state:

```bash
docker compose --env-file .env.prod.local -f compose.prod.yaml down --volumes
```
