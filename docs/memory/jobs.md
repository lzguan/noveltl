# Memory jobs

A memory job belongs to a memory group. The group determines its novel and
the language used for both explanatory memories and canonical term renderings.

## Configuration and creation

`POST /memory-agent/jobs` creates pending tasks; starting the job is a separate
operation. Chapter bounds are optional, start-inclusive and end-exclusive.
The frontend creates version 2 parameters:

```json
{
  "memoryGroupId": "<uuid>",
  "params": {
    "version": 2,
    "recordMemories": {
      "modelName": "deepseek:deepseek-v4-flash-low",
      "toolsets": {"glossary_terms": {}}
    },
    "translateTerms": {
      "modelName": "deepseek:deepseek-v4-flash-low"
    }
  }
}
```

Either stage may be omitted or null, but at least one must be configured.
Naming-only jobs can backfill existing and manually added terms. Version 1
parameters retain the original `modelName`/`toolsets` shape and resolve to
recording only. The migration adds `version: 1` to existing stored parameters
and assigns existing tasks to recording stage 0. Explicit versions are required
at the API boundary.

## Execution and ownership

Creation resolves the selected stages in recording-then-naming order and assigns
consecutive stage numbers. Each chapter receives a separate task for each selected
stage. Task identity is `(memory_job_id, chapter_id, stage_num)`. Each task's
stage number selects its configuration from the job parameters; the config's
stable name (`record_memories` or `translate_terms`) selects the behavior.
The frontend derives task labels from the job parameters and stage number.
Naming-only jobs therefore use stage number 0 with name `translate_terms`.

One worker claims a job and executes tasks sequentially by chapter then stage.
Each stage commits its memory changes together with its completed task status.
A failed stage rolls back its own writes and stops the run; earlier completed
stages remain committed. Starting again does not skip the failed stage.
Expired job claims can be replaced; stale owners cannot commit stage results.

`run_one_task` executes a selected pending stage. Existing task read/start/retry/
delete routes accept `stageNum` as a query parameter, defaulting to 0 for old
clients. A directly requested stage cannot bypass an unfinished preceding stage
in its chapter. Retry resets only the selected failed stage. After retrying it,
start the job to continue later pending work.

Task orchestration owns sessions, claims, input preparation, transactions, and
status. The thin functions in `agent/stages/` create the appropriate agent and
run it. Agent factories own prompts, model settings, capabilities, and output
schemas. Stages load the latest source chapter text when executed; agent run
context and source revisions are not pinned between stages.

The job UI reports stage-task counts and labels each row with its chapter and
stage. A separate term-translations interface is deferred.

## Naming behavior

Canonical renderings live in `term_translations`, keyed uniquely by glossary
term ID. Each row stores its rendering, review status, creator type, and creation/
update timestamps. Deleting a term cascades to its mapping. The target language
is inherited from the term's memory group; the rendering has no chapter validity
range or observed-content dependency. Pending and approved mappings are usable;
rejected source terms and rejected mappings are excluded from lookup.

Naming uses an atomic upsert that preserves every usable existing choice,
including pending human or agent choices. A rejected mapping may be replaced by
a new pending agent suggestion. Uniqueness also prevents concurrent naming jobs
from creating competing current rows. Dedicated translation review/edit UI is
still deferred; these rows do not appear in the ordinary memory review interface.

For terms occurring in the chapter, naming fills only missing usable mappings.
Existing mappings are never overwritten by the naming agent. The initial context
includes term kinds, established renderings for chapter terms and known aliases,
and bounded definition/relation context. Alias marks and traversal remain shared
with the glossary readers. Aliases are evidence for naming, not automatic reuse
of a different source form's rendering. Read-only tools can retrieve additional
definitions, relations, and translations.

The output schema rejects blank renderings and duplicate source forms. A typed
output validator registered by the agent factory checks exact coverage of the
requested terms; the capability stages the writes for task completion.
If no terms need naming, the task completes without agent
creation or a paid inference request. Real naming quality still requires separate
opt-in evaluation; deterministic tests cover the persistence and execution contract.
