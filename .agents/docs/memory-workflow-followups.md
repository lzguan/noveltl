# Memory workflow follow-ups

These are discussed directions after PR #129, not implemented behavior or an
approved detailed design. The current execution contract is in [memory jobs](memory-jobs.md).

## Conventions between recording and naming

The user suggested a future workflow:

`record memories → summarize conventions → translate terms`

The useful distinction is a barrier across the selected chapter range. Current
combined jobs interleave recording and naming per chapter. Merely adding another
chapter stage would not let early naming see conventions learned from the whole
range. Recording-only and naming-only jobs already provide two of the pieces.

A conventions pass could produce persisted, editable guidance covering personal
names, transformed identities, codenames, abbreviations, and terminology families.
The naming agent would consume that output explicitly. Its storage, schema,
review requirements, source range, and replacement behavior remain undecided.
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

This does not require parallel execution or a general workflow editor. The user
agreed to keep convention summarization and whole-job chaining outside PR #129.
