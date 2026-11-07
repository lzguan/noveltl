# AGENTS.md

Project for an automated novel translation project. Primarily targeted towards translating East Asian webnovels to English, though this scope may expand in the future. As such, this project is optimized for relatively short chapters, with anywhere between 100-10000 chapters in length.

## Project aims

Primary challenges this project aims to solve are consistency of translating names and writing style, as well as providing a suite of tools for humans to interact with different steps of translation.

## Project structure

Core services are split by responsibility:

- `backend/` - FastAPI application, database models, migrations, background-job logic, and tests
- `frontend/` - React application, UI components, route pages, and generated API client code
- `docs/` - technical documentation and design notes
- `.agents/docs/` - agent-maintained implementation notes and code navigation
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

Skills are currently located in [.agents/skills/](.agents/skills/) and tracked in [skills-lock.json](skills-lock.json).

Agent-maintained implementation notes live in [.agents/docs/](.agents/docs/README.md). Read its index and the notes relevant to your task. Keep code maps, implementation decisions, and agent handoff context there; reserve `docs/` for human-facing documentation. Verify notes against the code before relying on them, and update affected notes when implementation changes. This directory is a project convention, not an automatically discovered agent feature.

Do not create or modify human-facing documentation unless the user explicitly asks. Put agent-maintained implementation notes in `.agents/docs/` instead.

Do not mention `.agents/docs/` changes in pull request descriptions or other reviewer-facing summaries. Those notes are for agents, not human readers.

Use the [maintain-agent-docs skill](.agents/skills/maintain-agent-docs/SKILL.md) when creating or updating those notes.

Actively suggest ways for the user to improve their workflow, such as using plan mode, subagents, or various other features that you offer if they fit the task scope.

## Project scripts

- Frontend: `pnpm --dir frontend check` (type check), `pnpm --dir frontend lint` (ESLint), `pnpm --dir frontend test` (vitest). See [`frontend/package.json`](frontend/package.json) for more details.
- Backend: `uv --directory backend run ruff check` (lint), `uv --directory backend run pyrefly check` (type check), `uv --directory backend run pytest` (tests). See [`backend/pyproject.toml`](backend/pyproject.toml) for more details.

See [scripts.md](docs/scripts.md) for more scripts.

If any scripts time out, it may be due to lacking hardware. Confirm with the user before proceeding with a rerun.

## Other

If an issue is caused by a typo, describe it as a typo when communicating with the user. Do not overstate the severity of minor wording or spelling mistakes.

Excluding `as const` casts, don't cast variables without permission (i.e. don't use the `as` keyword on the frontend).

Don't write docstrings (module, class, or function) unless the user asks for them, except where an agent reads the text: pydantic-ai tool function docstrings, `Field(description=...)`, and docstrings on agent-facing models. When docstrings are wanted, follow the file's existing style; otherwise use Google style, stated declaratively (what it does, its contract, errors), without design rationale.

Don't add `__init__.py` files; backend packages are namespace packages.

If you are running into issues connecting with the test database/external services, it may be because you are running a command in a sandbox. Escalate the request to the user in that case.

If you decide to use database locks raise that to the user. Almost certainly there is a way to do it without locks.
