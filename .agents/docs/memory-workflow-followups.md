# Memory workflow follow-ups

Discussed directions, not implemented behavior or an approved design. Current
behavior is in [memory jobs](memory-jobs.md) and
[translation conventions](translation-conventions.md).

## Conventions

- **Chapter translation does not read term translations or conventions**
  (`iter_batch_memories` is its only memory input). Wiring established
  renderings, then conventions, into the translate prompt is what makes naming
  and conventions output reach translated text.
- **Windowed schedules:** a params option compiled into the schedule queries,
  e.g. record N chapters, conventions, name N, so conventions cadence and stage
  barriers share one mechanism. Stages already run as job-wide barriers.
- **Agent inputs:** a chapter-excerpt tool (style needs prose evidence), alias
  reads, possibly selectable toolsets; keep tools pluggable rather than
  growing the context. The job form does not set `since_chapter_num` yet.
- **Dry-run naming as input:** name first so the agent resolves observed
  rendering variance. `term_translations` has no job provenance, so keep drafts
  out of the table rather than persisting and clearing them. V3 params allow
  two naming stages in one job.
- Flagging existing mappings that conflict with a convention is deferred.
  A free-text summary does not by itself fix retrieval or source matching; see
  [observed cases](naming-observations.md).

## Dependencies between whole jobs

No table or completion trigger exists. Keep this separate from `stage_num`
(execution order inside one job). Settle what success means for a
prerequisite, which job types and ranges may connect, and how changed upstream
output affects dependents. Guarantees to design for: dependents wait for
successful completion (failure or abort does not count); duplicate completion
handling does not launch duplicate work; retries stay local to each job; cycles
are impossible. Sketch: `memory_job_dependencies(job_id, depends_on_job_id)`
written only at creation, a completion check on every task-completion path, and
a conditional update guarding dependent dispatch instead of locks.

## Story arcs

Quick-transmigration and infinite-flow novels need per-world scoping. Glossary
terms are unique per `(group, term)`, so one name in different worlds collapses
into one term. A first-class arc (e.g. nullable `arc_id`, null meaning global)
could scope terms, memories, and conventions. Chapter ranges fit contiguous
worlds but not recurring instance types. Untested workaround: a memory group per
world.

## Configuration defaults (far future)

Defaults for toolsets, conventions cadence, and guidance could eventually come
from novel features. Data is too scarce and noisy now (identical naming runs
differed on 9–21 of 82 terms). Order: hand-curated genre presets; a structured
per-job run summary so data accumulates; per-novel calibration on early
chapters; cross-novel fitting only once enough scored runs exist.

## Job ownership and agent access

Memory and translation jobs store no user; access is checked only through the
memory group when a job is created or started, so a job acts with its group's
reach rather than its creator's (revoked users' jobs still run). Unverified:
whether memory-group edit access always implies reading every chapter an agent
reads. Possible fix: nullable `created_by` on jobs and `source_job_id` on
agent-written rows. Deferred by the user (2026-11-07).
