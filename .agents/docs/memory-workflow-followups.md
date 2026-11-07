# Memory workflow follow-ups

These are discussed directions after PR #129, not implemented behavior or an
approved detailed design. The current execution contract is in [memory jobs](memory-jobs.md).

## Conventions between recording and naming

The user suggested a future workflow:

`record memories → summarize conventions → translate terms`

The useful distinction is a barrier across the selected chapter range. Stages
now run as job-wide barriers ([memory jobs](memory-jobs.md)), so a conventions
stage between recording and naming would see the whole range before any naming.
Planned next: an order spec in job params V3 compiled into the schedule queries,
e.g. windows of N chapters (record N, conventions, name N) so conventions cadence
and barriers share one mechanism, reducing the need for job chaining.

Storage, the review UI, and naming consumption now exist; see
[translation conventions](translation-conventions.md). The conventions stage is
scaffolded but unimplemented: a `summarize_conventions` stage config,
one anchored task per job ([memory jobs](memory-jobs.md)), and stub
[agent](../../backend/src/memory/agent/agents/conventions.py) and
[stage](../../backend/src/memory/agent/stages/conventions.py) modules that raise
`NotImplementedError`. The job form offers it, so such jobs fail at that task
until the agent exists.

Decided with the user (2026-11-06), not yet implemented:

- Scope: a run covers terms occurring in chapters [`since_chapter_num`,
  anchor] (`SummarizeConventionsConfig.since_chapter_num`; None means the first
  chapter; the form is expected to fill in the job's start). "Strictly new"
  terms were rejected as the precomputed input: checking that a term is absent
  from all earlier chapters costs a scan of the whole novel per term (about
  1.6 s for 85 terms over 856 chapters / 2.7M characters on the dev database).
  Instead the agent asks for history per term. Exact text search lives at the
  novels level in [term_search.py](../../backend/src/novels/term_search.py)
  (also served as `GET /novels/{novelId}/term-search` and
  `GET /chapter-contents/{chapterContentId}/term-search`); an agent occurrence
  tool should reuse it and pass the anchor chapter as the range end, which keeps
  the no-spoiler rule on the memory side. `access.search_terms` searches term
  names. No agent tools exist yet.
- Output (implemented in [capabilities/conventions.py](../../backend/src/memory/agent/capabilities/conventions.py),
  not yet wired to a real agent): `ConventionsOutput` with create / revise /
  withdraw by handle. Handles come from `MemAgentDeps.convention_handles`, a
  `UUIDCache(prefix="c")` beside `memory_handles`, so the context and any tool
  hand out the same `c3` within a run. `write_conventions_output` is the output
  validator and the only write path: in a savepoint it inserts creates and
  calls access `update_convention` / `delete_convention` with
  `only_creator=AGENT, only_pending=True`. An unknown handle or a zero-row match
  rolls back the whole attempt and raises `ModelRetry` (pydantic-ai reports it
  on the output tool's return part, not as a `RetryPromptPart`); otherwise the
  savepoint is kept and commits with the task. Checking and writing are one
  step, so there is no separate permission read to race with. Withdraw deletes
  the row. The user service keeps its own inline statements, because it wraps
  them with `convention_mod_access_*` before executing.
- Naming in the same job follows the agent's pending conventions (naming already
  reads pending + approved).
- First input is term-centric, built by `conventions_context` in
  [toolsets/conventions/context.py](../../backend/src/memory/agent/toolsets/conventions/context.py):
  the group's naming conventions (rejected ones included) with handles
  registered in `deps.convention_handles`, and up to 200 terms occurring in
  [since, anchor] (`glossary.get_terms_in_chapter_range`, ordered by first
  occurrence, with a `terms_truncated` flag) carrying kind, first chapter, the
  newest active definition (from `inspect_terms`, cut to 200 characters), and
  the current translation. A chapter cursor for paging terms was tried and
  dropped: windows rarely approach 200 terms (85 recorded terms for 下班…
  chapters 1-49). The user wants room to add read tools later (chapter excerpts,
  term occurrences, aliases, possibly selectable toolsets), so keep the agent's
  tools pluggable rather than baking more into the context.

Alternative input considered: a dry-run naming stage first, so the agent
resolves observed rendering variance. `term_translations` has no job
provenance, so do not persist and later clear the dry run. V3 params allow two
naming stages in one job.

Flagging existing mappings that conflict with a convention is deferred.
Do not assume a new free-text summary automatically fixes retrieval or source
matching; see the separate [observed cases](naming-observations.md).

## Dependencies between whole jobs

A possible representation is an association between prerequisite and dependent
jobs. No such table or completion trigger exists today. Keep this separate from
the current meaning of `stage_num`: execution order inside one job, not a fixed
task-type identifier or cross-job dependency.

Before implementation, settle what success means for a prerequisite, which job
types/ranges may connect, and how a changed upstream output affects downstream
work. Useful guarantees to design for include:

- A dependent waits for successful prerequisite completion; failure or abort
  does not count as success.
- Retried or duplicate completion handling does not launch duplicate work.
- Retry progress remains local to each job; restarting naming need not rerun
  successful recording.
- Invalid dependencies and cycles are rejected if the interface permits them.

This does not require parallel execution or a general workflow editor. In-job
"passes" (stage-first ordering) were considered and rejected in favor of
chaining. A discussed sketch: `memory_job_dependencies(job_id,
depends_on_job_id)` written only at creation (so no cycles), a completion check
on every task-completion path, and a conditional update guarding dependent
dispatch instead of locks. Planned as a separate PR.

## Story arcs

Quick-transmigration and infinite-flow novels need per-world scoping. Glossary
terms are unique per `(group, term)`, so the same name in different worlds
collapses into one term; that is the harder problem. A first-class arc concept
could later scope glossary terms, memories, and conventions (e.g. a nullable
`arc_id` where null means global). Chapter ranges alone fit contiguous worlds
but not recurring instance types. One untested workaround is a memory group
per world.

## Configuration defaults (far future)

Discussed, not planned. Defaults such as toolsets, conventions cadence, and
guidance could eventually come from novel features (genre, chapter length,
chapter count, term density). Data is too scarce and noisy for a model now:
identical naming runs differed on 9–21 of 82 terms (see
[translation conventions](translation-conventions.md)). Suggested order:
hand-curated genre presets; a structured per-job run summary (config, novel
features, cost, failures, term counts, later eval scores) so data accumulates;
per-novel calibration of a few configs on early chapters; cross-novel fitting
only once enough scored runs exist.

## Job ownership and agent access

Memory jobs (and translation jobs) store no user; access is checked only
through the memory group when a job is created or started. Agents therefore
act with the job's reach, not the starting user's: a user whose access is
revoked can still have their job run, and it is unverified whether memory-group
edit access always implies read access to every chapter the agent reads.
Agent-written rows are marked only `creator_type=AGENT`, so "the agent's own
pending conventions" means any agent run's, not one job's. A possible fix is a
nullable `created_by` on jobs plus a `source_job_id` on agent-written rows;
deferred by the user (2026-11-07).
