# AGENTS.md

Project for an automated novel translation project. Primarily targeted towards translating East Asian webnovels to English, though this scope may expand in the future. As such, this project is optimized for relatively short chapters, with anywhere between 100-10000 chapters in length.

## Project aims

Primary challenges this project aims to solve are consistency of translating names and writing style, as well as providing a suite of tools for humans to interact with different steps of translation.

## Project structure

Core services are split by responsibility:

- `backend/` - FastAPI application, database models, migrations, background-job logic, and tests
- `frontend/` - React application, UI components, route pages, and generated API client code
- `docs/` - technical documentation and design notes
- repo root config - local environment and multi-service setup such as `compose.yaml` and devcontainer files

Depending on the user, this project may be developed inside a devcontainer. See [.devcontainer](.devcontainer/), [compose.yaml](compose.yaml), and the Dockerfiles for config info.

The [docs](docs/) folder contains project documentation. Read [docs/README.md](docs/README.md) for a high-level overview and entry points into the relevant technical docs.

If you plan to work on any technically challenging task, read the documents most relevant to that feature before making changes.

Docs may lag behind implementation. If a document appears inconsistent with the code or current task, verify against the codebase and raise the discrepancy to the user. Documentation is primarily meant to facilitate onboarding to the project, not to record every last detail.

## Editing

For edits with broader scope, confirm with the user before proceeding. This includes changes spanning several files, large changes within a file, or changes that may affect architecture, data flow, or public behavior.

Before any such edit, remind the user to make a git commit first.

When debugging, if the issue turns out to be more subtle or require a broader fix than initially expected, explain the new findings and your proposed fix before making further edits.

## Skills/Agents

Skills are currently located in [.claude/skills/](.claude/skills/). Agents are currently located in [.claude/agents/](.claude/agents/). If none of the above conventions fits the format that your tool expects, let the user know at the beginning of a session.

Actively suggest ways for the user to improve their workflow, such as using plan mode, subagents, or various other features that you offer if they fit the task scope.

## Project scripts

- Frontend: `pnpm --dir frontend check` (type check), `pnpm --dir frontend lint` (ESLint), `pnpm --dir frontend test` (vitest). See [`frontend/package.json`](frontend/package.json) for more details.
- Backend: `uv --directory backend run ruff check` (lint), `uv --directory run pyrefly` (type check), `uv --directory run pytest` (tests). See [`backend/pyproject.toml`](backend/pyproject.toml) for more details.

See [scripts.md](docs/scripts.md) for more scripts.

If any scripts time out, it may be due to lacking hardware. Confirm with the user before proceeding with a rerun.

## Other

If an issue is caused by a typo, describe it as a typo when communicating with the user. Do not overstate the severity of minor wording or spelling mistakes.