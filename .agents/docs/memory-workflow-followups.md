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
  Instead the agent asks for history per term. The data access exists in
  [occurrences.py](../../backend/src/memory/plugins/glossary/occurrences.py)
  (`get_terms_in_chapter_range`, `get_term_occurrences`, both on latest chapter
  content and never past the anchor) and `access.search_terms`; agent tools for
  them do not exist yet.
- Output: structured create / revise / withdraw by short handle, with an output
  validator enforcing "agent-created and still pending" (retry otherwise), not
  write tools. Apply revisions and withdrawals with statements that repeat that
  condition, so a convention a user edits mid-run is not overwritten.
- Naming in the same job follows the agent's pending conventions (naming already
  reads pending + approved).
- First input is term-centric: new terms (kind, short definition), existing
  conventions by handle (rejected ones included so they are not re-proposed),
  related translations, and a substring/morpheme term search for families such
  as rank ladders. The user wants room to add read tools later (chapter
  excerpts, term occurrences, aliases, possibly selectable toolsets), so keep the
  agent's tools pluggable rather than baking the context into one prompt.

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
