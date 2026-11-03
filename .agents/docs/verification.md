# Verification entry points

Follow the root [AGENTS.md](../../AGENTS.md) for execution constraints and
[docs/scripts.md](../../docs/scripts.md) for the maintained command reference.
Use the [test-writing skill](../skills/test-writing/SKILL.md) when selecting,
writing, or changing regression coverage.

## Scope

The [memory-job](memory-jobs.md) and [term-translation](term-translations.md) notes
link to focused tests. Backend database behavior needs the real PostgreSQL
fixtures. Task tests replace paid inference with Pydantic AI test/function models;
passing them does not establish naming quality.

Backend changes should run relevant tests and lint/type checks. Pure file moves
or import changes can use static checks and a runtime import check. Documentation
changes need link/path checks and `git diff --check`.

## API generation

After a public schema change, run both steps from the repository root:

```bash
uv --directory backend run --no-sync python -m scripts.extract_openapi
pnpm --dir frontend generate:api
```

Review OpenAPI and generated client changes together. The frontend generator
temporarily removes generated directories before rebuilding them; wait for it
to finish before interpreting the diff or running dependent checks. Do not edit
generated files manually.

Internal config/context changes do not inherently change OpenAPI. Check the
actual schema before regenerating clients for such a change.

For frontend behavior changes, use the
[frontend-conventions skill](../skills/frontend-conventions/SKILL.md). Commands
are listed in [frontend/package.json](../../frontend/package.json).
