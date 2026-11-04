# Canonical term translations

## Source map

| Responsibility | Source |
| --- | --- |
| Translation table and shared accessors | [plugins/translations/](../../backend/src/memory/plugins/translations/) |
| Typed naming context and read-only agent tool | [toolsets/translations/tools.py](../../backend/src/memory/agent/toolsets/translations/tools.py) |
| Naming instructions and request formatting | [prompts/term_translation.py](../../backend/src/memory/agent/prompts/term_translation.py) |
| Agent output schema and staged writes | [capabilities/term_translation.py](../../backend/src/memory/agent/capabilities/term_translation.py) |
| HTTP endpoints and permission-aware mutations | [router.py](../../backend/src/memory/plugins/translations/router.py), [service.py](../../backend/src/memory/plugins/translations/service.py) |
| Page loading and local mapping updates | [useGlossaryTerms.ts](../../frontend/src/memory/hooks/useGlossaryTerms.ts) |
| Translation editing and review controls | [TermTranslationEditor.tsx](../../frontend/src/memory/components/TermTranslationEditor.tsx) |

Naming tools use glossary accessors for terms, definitions, relations, and aliases.
Translation SQL belongs to the shared translation plugin. Canonical mappings
are not yet integrated into chapter-translation actions.

## Storage and review

`term_translations` is keyed by glossary `term_id`; deleting the term deletes its
translation. The target language comes from the memory group. Renderings have no
chapter validity interval.

Agent reads use exact source forms in one group. Both the source term and translation
must be non-rejected. Pending and approved translations are usable. The naming
upsert preserves either, regardless of creator. It can replace a rejected
translation with a pending agent suggestion. Writes stay in the caller's
transaction until [task completion](memory-jobs.md).

The review API instead batch-reads up to 100 term IDs and includes rejected
mappings. Manual saves preserve existing review status, set creator to user,
and create missing mappings as pending. Review-status updates preserve the
text and creator. Deletion removes only the mapping. All mutations require
edit access to the source term's memory group.

## Context and output

`term_translation_context` finds glossary terms occurring in the chapter and
returns `TermTranslationContext | None`. `requested_terms` contains only terms
missing usable translations. If none are missing, it returns `None`, and task
execution skips the agent.

Context also includes usable translations for chapter terms and their known
aliases, plus bounded definition/relation context. Stages with
`include_conventions` also receive the group's naming
[conventions](translation-conventions.md). Alias evidence does not make
another source form's rendering an exact mapping. Alias traversal and accepted
marks remain owned by glossary accessors.

The accepted marks are centralized in `access.ALIAS_MARKS`: plain `alias`,
`alias.spelling`, `alias.persona`, and `alias.transformation`. The plain mark
is accepted for untyped alias edges; this does not establish that older rows
exist. Do not scatter prefix matching or additional mark lists across callers.

Context models live beside the helper in `tools.py`. Keep them typed through
execution and serialize only in the prompt builder. The stage derives the exact
required source names from `requested_terms` when creating the agent.

Output-model validation rejects blank translations and duplicate source names.
The factory's typed output validator checks exact requested-term coverage and
uses the agent's existing retry semantics. The capability stages database writes;
it does not commit them.

## Frontend and context pitfalls

Both the glossary and Term translations views fetch a glossary term page,
then one batch of mappings for that page. The glossary displays previews;
the dedicated view exposes approve, reject, and delete controls. Successful
mutations update the local mapping map without refetching the source terms.

Chapter matching uses glossary `contains_query`, which strips only its listed
obfuscation marks. A stored term that differs from the source's punctuation
can be missed by naming. Terms absent from the glossary cannot be translated
by this stage. Missing definition associations or abbreviation aliases can
hide relevant older context even when it exists elsewhere in the group.
Successful stage completion does not establish translation quality.
See [naming observations](naming-observations.md) for source-backed examples
and the distinction between missing context, missing source terms, and style.

## Tests

- [Access/context](../../backend/tests/memory/test_term_translations.py): aliases, review status, uniqueness, and deletion.
- [Tasks](../../backend/tests/memory/test_memory_agent_tasks.py): naming retries and skipping agent creation.
- [API](../../backend/tests/memory/test_term_translation_router.py): permission checks, batch scoping, manual saves, review, and deletion.
- [UI](../../frontend/src/memory/components/TermTranslations.test.tsx): page batching, editing/review/deletion, error handling, stale responses, and pagination.
