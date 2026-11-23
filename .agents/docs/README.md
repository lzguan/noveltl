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
| Change translation conventions, their naming use, or the conventions agent | [Translation conventions](translation-conventions.md) |
| Plan chapter-translation wiring, windowed schedules, job chaining, or story arcs | [Memory workflow follow-ups](memory-workflow-followups.md) |
| Choose checks or regenerate API contracts | [Verification](verification.md) |
| Change the analytics store, translation-job export, or loader | [Analytics store](analytics.md) |
| Plan eval framework work or the translation calibration loop | [Evaluation plans](evaluation-plans.md) |
| Review early memory-agent design decisions and evaluations | [Memory-agent design history](memory-agent-design-history.md) |
| Plan the reader app or translation publishing | [Reader plans](reader-plans.md) |
| Pick up the current short-term work list (async backend, promotion jobs, permissions, feedback) | [Short-term plan](short-term-plan.md) |

The root [AGENTS.md](../../AGENTS.md) contains project instructions. This folder
is discovered through those instructions, not special directory handling.

Keep one owner for each topic and link to it from other notes. Record decisions
and pitfalls that a future agent would otherwise have to rediscover. Keep command
output, session transcripts, and temporary investigation logs out of these notes.

Use [maintain-agent-docs](../skills/maintain-agent-docs/SKILL.md) when creating,
refreshing, or consolidating notes.

Code audit: 2026-11-03, after PR #129. Recheck the linked implementation when using a note.
