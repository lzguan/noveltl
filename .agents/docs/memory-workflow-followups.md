# Memory workflow follow-ups

Discussed directions, not implemented behavior or an approved design. Current
behavior is in [memory jobs](memory-jobs.md) and
[translation conventions](translation-conventions.md).

## Conventions

- **Chapter translation prompts do not consume term translations or conventions.**
  The loader can snapshot both as streams; wiring those streams into the
  translate prompt is what makes naming and conventions output reach translated text.
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

## Failure logging and workspace cleanup

Failed tasks get one `logger.exception` line in `arun_tasks`; the JSONL result
sink in [celery.py](../../backend/src/memory/agent/dispatch/celery.py) records
only completed and skipped tasks. A `memoryAgent.failed` event would have two
shapes: the full `AgentRunResult` when publication fails after a finished run,
and a partial transcript from `capture_run_messages` when `agent.run` raises.
Orphan workspaces (crash, failed cleanup, failed commit verification) have no
reaper; a periodic delete of workspaces whose task is not processing would do.
Both deferred by the user until before production (2026-11-12).

## Publication merge policy

Publication is last write wins, so a review or edit made during a run is
overwritten (approvals revert, guarded convention/translation updates apply
unconditionally). The user accepts this until a merge policy is chosen
(2026-11-12); do not re-raise it as a defect.

## Existing partial translations as input

Considered and deferred by the user (2026-11-13). Three distinct uses: earlier
translated chapters as a style/consistency reference for chapter translation; a
rough translation of the same chapter as a draft to revise; and source/translation
alignment as evidence for term naming (memory side, feeding the planned `terms`
stream). The first two are extra translation-job input streams of type `chapter`
under another name, i.e. the first case needing stream names distinct from types.
Unverified: how translated novels map chapter-to-chapter onto their source work.

## Recording as structured output

Considered 2026-11-14; the user prefers to leave tool-based recording as is.
The appeal is one request per chapter (batch-API eligible, one atomic write,
a single diffable artifact per chapter). The user's concerns: shadow workspaces
already solve the transaction problem and should stay until shown to be a
liability, and a single schema covering every memory kind is unlikely to be
filled reliably by small models. A structured stage would still stage through
workspaces, and would need per-chapter retrieval of relevant terms/memories with
handles, since on-demand reads disappear. If recording cost becomes the
bottleneck, the proposed experiment is one narrow pass (e.g. term extraction)
compared against tool-based output on already-recorded chapters, not a single
large schema. Unmeasured: how many requests and read-tool calls recording uses
per chapter today (the worker's result log records both).
