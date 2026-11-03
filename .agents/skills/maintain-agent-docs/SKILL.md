---
name: maintain-agent-docs
description: Create, refresh, or consolidate this project's implementation notes in .agents/docs when recording handoff knowledge or correcting stale notes. Use for agent documentation maintenance, not general human-facing documentation.
---

# Maintain agent docs

Keep `.agents/docs/` useful for the next coding task: code navigation,
non-obvious contracts, decisions, and demonstrated pitfalls. Start with its
[index](../../docs/README.md) and the notes relevant to the changed feature.
The human-documentation boundary is defined in the root [AGENTS.md](../../../AGENTS.md).

## Select what belongs

- Record knowledge that would otherwise require rediscovering a call path,
  ownership boundary, configuration adapter, transaction rule, or failure mode.
- Link to the implementation or faithful tests instead of copying code,
  complete schemas, or long command inventories.
- Keep one topic owner. Update or remove a stale paragraph rather than adding
  a contradictory explanation elsewhere. Add an index entry for a new topic.
- Keep raw logs, source corpora, credentials, session transcripts, and temporary
  investigation output out of the notes. Condense a useful observation to its
  trigger, evidence, consequence, and verification limits.

## Verify claims

Read the relevant implementation before changing a behavioral claim. A prior
note, old branch, planned run configuration, or successful structural test is
not evidence that a behavior currently exists or that model output is tuned.

Distinguish current behavior, observed limitations, and proposals. For a proposal,
record the motivating case and unsettled decisions without presenting suggestions
as user requirements or completed work. For model evaluations, keep the model,
scope, evidence, and limits needed to interpret the conclusion; separate task
success from output quality and user aborts from inference failures.

Mark local artifacts and database IDs as environment-specific. Prefer tracked
code/test links for durable navigation; do not require an ignored log or private
corpus to understand the note.

## Check and finish

Resolve relative file links from the file containing them. Check new index links
and links in any moved notes. Search edited notes for references to removed
symbols or paths and run `git diff --check`. Documentation-only changes need
path/link checks, not a rerun of application suites.

Review the final diff for accidental human-doc edits and claims that go beyond
the evidence. Report the maintained topics and any unresolved uncertainty. Follow
the user's existing commit/PR instructions; maintaining a note does not itself
authorize pushing, merging, or changing application code.
