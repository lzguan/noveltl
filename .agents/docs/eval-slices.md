# Eval database slices

A slice is a whole database state "as work had reached chapter N", built from a
seed database for one eval case. Code: [spec.py](../../evals/src/evals/slices/spec.py),
[materialize.py](../../evals/src/evals/slices/materialize.py),
[settings.py](../../evals/src/evals/slices/settings.py); tests in
[evals/tests/slices/](../../evals/tests/slices/). Design settled 2026-11-16 with
a second-model review; the broader eval direction is in
[evaluation plans](evaluation-plans.md).

## Packaging boundary

`evals/` is its own uv project depending on the backend as an editable path
dependency. `evals.slices` may import only the backend, pydantic and the
standard library, never other `evals` modules, so it can be split out later;
`test_slices_imports_nothing_else_from_evals` enforces this. The destructive cut
deliberately lives outside `backend/src/`.

Editor type checking reports false `ColumnElement`-not-assignable-to-`ColumnElement`
errors in `evals/` files: the language server checks backend files with
`backend/.venv` and evals files with `evals/.venv`, creating two copies of each
shared class (upstream pyrefly-org/pyrefly#3556). Command-line `pyrefly check`
inside `evals/` is correct. Pinning versions does not help; issue #140 proposes
a single uv workspace.

## Spec

`Slice(horizon, novels, groups)`. Horizons are inclusive chapter numbers:
`None` means no cut, `False` (per table only) means exclude, and an unset field
(pydantic `MISSING`) inherits from the level above: table keys from the group's
`horizon`, which inherits `Slice.horizon`. Chapter numbers are strict ints,
because lax mode would read `false`/`true` as chapters 0/1. Unknown keys fail
(`extra="forbid"`).

- `GroupSlice` keys are per table, not per plugin: `terms`, `term_translations`,
  `memories`, `conventions`. Continuity summaries share `memories` and are
  separated only by `plugin_name`, so per-plugin keys could not express
  independent term and memory horizons.
- `NovelSlice` lists only novels to truncate (prior-translation novels). Unlisted
  novels and all source chapters are copied in full, since the task needs later
  chapters as input. The horizon is a raw chapter number and assumes 1:1
  numbering with the source; nothing checks this.
- Static checks: each novel/group once; `term_translations` and `memories` may not
  extend past `terms` (`None` = +inf, `False` = -inf).

## Materialize

`materialize(seed_url, spec, *, name=None)` runs `CREATE DATABASE <name> TEMPLATE
<seed>` on the seed's server, then does every check and cut inside the copy and
drops the copy on any failure. IDs equal the seed's, so no ID map exists, and
one group cannot appear at two horizons. The caller (eval runner) chooses `name`
to recognise its own databases for keep-up/cleanup; slices only offers `drop`.

Pre-checks: no other connections to the seed (the seed must not be the
`postgres` maintenance database); `alembic_version` equals the code's head;
no pending/processing memory tasks or unfinished, unfailed translation tasks
(a worker on the copy could resume them; not covered by tests); listed
novels/groups exist; a truncated novel has no memory group (unlinking would make
its rows look always-present and orphan continuity summaries).

Cut rules per group:
- terms, translations, conventions: keep if `recorded_on` is null or its chapter
  number <= horizon;
- memories: keep if `memory_start_num` <= horizon, then clear `memory_end_num`
  above it; supersede targets always start earlier, so chains cannot break;
- associations: dropped whenever either side is cut (derived edges, never an error).

Data checks run before any delete, because term deletion cascades to
translations and would hide them: fail on a translation kept for a cut term, or a
memory that had terms in the source and keeps none. Truncating a novel first
deletes `labels`, `label_datas` and `auto_labels`, which reference chapter
contents without `ondelete`.

`MaterializedSlice.counts` gives per-table `CutCounts(kept, cut, kept_null)`.
Rows recorded before migration `74a4a10cb394` have null `recorded_on` and are
always kept, so for older data a term/translation/convention horizon is a no-op;
`kept_null` makes that visible. No fallback (e.g. a term's earliest memory
chapter) is implemented.

Copies share the seed's object-storage keys (`{namespace}/{file_id.hex}`): new
writes cannot collide, but any future file cleanup in a copy would delete the
seed's objects.

## Chapter provenance (`recorded_on`)

Nullable chapter-content FK with `ON DELETE SET NULL` on `glossaries`,
`term_translations`, `translation_conventions` and their shadow tables;
`memories.memory_observed_in` was made nullable with SET NULL in the same
migration (`shadow_memories` keeps CASCADE). Agent writes set it from
`MemAccessContext.chapter_content_id`; the conventions task's context is the
range's last chapter, so a convention is only accurate at job boundaries.
Agent rewrites (re-translating a rejected mapping, revising a pending convention)
bump it to the current chapter; user writes leave it unchanged or null. Rows are
edited in place, so a bump loses the creation chapter. The user considers these
semantics provisional ("a way to take slices"); improving them is non-urgent.

## Seed database

Compose service `evals_db` (database `seed`, trust auth, no published port);
`EVALS_DB_URL` reaches the dev container. Migrate it with
`DB_URL=$EVALS_DB_URL uv --directory backend run alembic upgrade head`; fill it by
running the app and workers against it. Dumps of it carry `alembic_version`, so
backups taken before the pre-deploy migration squash cannot be upgraded after it.

## Deferred

Next agreed step: design a seed-data CLI and a slice CLI (list/show/add/delete,
`materialize`/drop, JSON output, non-interactive) before filling the seed.
Slices, source labels and probably cases should live in the seed database, not
git, so a checkout without the data yields no cases instead of errors; eval
reports should then state skipped-case counts. Also deferred: forking one group
at two horizons, combining sources from other databases, null fallbacks,
history for in-place edits, and horizons for chapter translations once they
become pipeline inputs.
