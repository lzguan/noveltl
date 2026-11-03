# Agent implementation notes

This directory holds implementation notes for coding agents. Human-facing
documentation stays in `docs/`.

Verify notes against the source code before relying on them. Prefer links to
code and tests over copied implementations, and update notes when the behavior
they describe changes.

| Task | Read |
| --- | --- |
| Change editor synchronization, content revisions, or label porting | [Editor persistence](editor-persistence.md) |
| Change chapter-translation actions, artifacts, or recovery | [Chapter translation](chapter-translation.md) |
| Find worker entry points or change object storage | [Background services and files](background-services.md) |
| Change memory-job configuration, ordering, claims, or retries | [Memory jobs](memory-jobs.md) |
| Change term naming, translation storage, or glossary review UI | [Term translations](term-translations.md) |
| Investigate naming quality or choose a regression case | [Naming observations](naming-observations.md) |
| Explore conventions passes or dependencies between jobs | [Memory workflow follow-ups](memory-workflow-followups.md) |
| Choose checks or regenerate API contracts | [Verification](verification.md) |

The root [AGENTS.md](../../AGENTS.md) contains project instructions. This folder
is discovered through those instructions, not special directory handling.

Keep one owner for each topic and link to it from other notes. Record decisions
and pitfalls that a future agent would otherwise have to rediscover. Keep command
output, session transcripts, and temporary investigation logs out of these notes.

Use [maintain-agent-docs](../skills/maintain-agent-docs/SKILL.md) when creating,
refreshing, or consolidating notes.

Code audit: 2026-11-03, after PR #129. Recheck the linked implementation when using a note.
