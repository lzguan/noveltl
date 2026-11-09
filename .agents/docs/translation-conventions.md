# Translation conventions

Novel-level guidance for one memory group's target language, written by users
and by the conventions agent. Conventions are global rules, not per-term data or memories.

## Source map

| Responsibility | Source |
| --- | --- |
| Table and category enum | [plugins/conventions/models.py](../../backend/src/memory/plugins/conventions/models.py), [types.py](../../backend/src/memory/plugins/conventions/types.py) |
| Shared data access (no permissions, no commits) | [plugins/conventions/access.py](../../backend/src/memory/plugins/conventions/access.py) |
| Permission helpers, user service, HTTP routes | [permissions.py](../../backend/src/memory/plugins/conventions/permissions.py), [service.py](../../backend/src/memory/plugins/conventions/service.py), [router.py](../../backend/src/memory/plugins/conventions/router.py) |
| Agent output and writes | [capabilities/conventions.py](../../backend/src/memory/agent/capabilities/conventions.py) (`write_conventions_output`); `update_convention` / `delete_convention` in access.py take `only_creator` / `only_pending` filters |
| Conventions agent (context, prompt, tools, factory, runner) | [toolsets/conventions/](../../backend/src/memory/agent/toolsets/conventions/), [prompts/conventions.py](../../backend/src/memory/agent/prompts/conventions.py), [agents/conventions.py](../../backend/src/memory/agent/agents/conventions.py), [stages/conventions.py](../../backend/src/memory/agent/stages/conventions.py) |
| Naming consumption | [toolsets/translations/tools.py](../../backend/src/memory/agent/toolsets/translations/tools.py), [prompts/term_translation.py](../../backend/src/memory/agent/prompts/term_translation.py), [agents/term_translation.py](../../backend/src/memory/agent/agents/term_translation.py) |
| Review UI | [ConventionsBrowser.tsx](../../frontend/src/memory/components/ConventionsBrowser.tsx), [useConventions.ts](../../frontend/src/memory/hooks/useConventions.ts) |
| Job option | [CreateMemoryJobForm.tsx](../../frontend/src/memory/agent/components/CreateMemoryJobForm.tsx) |

## Decisions

- Stored in `translation_conventions`, not `memories`: conventions are not
  chapter-gated, so they avoid `write_memory`'s start-chapter coupling,
  `end_num` supersede rules, and leaking into chapter translation via
  `iter_batch_memories`.
- Fields: `category` (`naming` | `style`), `title`, `rule`, nullable
  `rationale`, `review_status`, `creator_type`. No chapter range, slug, or term
  membership. Examples belong in the rule text for now. A separate examples
  table is deferred unless examples need independent evidence/review/retrieval;
  prompt guidance is the current approach to keeping rules compact.
- Arc scoping (quick-transmigration worlds, infinite-flow instances) was
  considered and deferred to a future arc concept shared with the glossary; see
  [follow-ups](memory-workflow-followups.md).
- `access.py` executes statements beneath both the user service and the agent
  and applies no caller policy; it raises `ConventionNotFoundException` when a
  conditional update or delete matches nothing. The service scopes statements with the
  `convention_mod_access_*` helpers. Manual edits set `creator_type=user`;
  review-status changes keep the creator.
- Lists include rejected rows unless `reviewStatuses` filters them. Without read
  access the list is an empty page, matching memory listings.

## Naming consumption

`TranslateTermsConfig.include_conventions` defaults to false so stored jobs keep
their behavior. When enabled, `term_translation_context` adds the group's
pending and approved naming conventions (`AgentConvention`: title, rule,
rationale), and the naming agent receives
`TERM_TRANSLATION_CONVENTIONS_INSTRUCTIONS`. When disabled, both the context JSON
and the instructions are unchanged. Chapter translation reads no conventions
(and no term translations) yet, so style conventions have no consumer.

## Conventions agent

A `summarize_conventions` stage (one task on the range's last chapter; see
[memory jobs](memory-jobs.md)) reviews chapters [`since_chapter_num`, anchor];
an unset start means the first chapter.

- Context (`conventions_context`): every convention in the group, rejected ones
  included, each with a handle from `MemAgentDeps.convention_handles`
  (`UUIDCache(prefix="c")`), plus up to 200 glossary terms occurring in the
  range (`glossary.get_terms_in_chapter_range`, by first occurrence) with kind,
  first chapter, newest active definition (cut to 200 characters), and current
  translation. The runner skips the model when no terms occur; the range is
  stated in the request prompt from the task's chapter number.
- Tools: `search_glossary_terms`, `term_occurrences`
  (`plugins/term_search/access.py` `count_text_occurrences`, up to the anchor, any text), and
  the existing definitions, relations, and translations reads. No chapter
  excerpts, so style evidence is weak.
  `term_occurrences` validates each searched string as nonempty; invalid tool
  arguments are returned to the model for correction. The underlying
  `count_text_occurrences` also rejects empty strings with `ValueError` before
  querying, so direct callers cannot trigger SQL division by zero. An empty
  input list still returns no results; nonempty whitespace is searched literally.
- Output: `ConventionsOutput` create / revise / withdraw, each draft with a
  `category` (naming or style). `write_conventions_output` is the output
  validator and the only write path: in a savepoint it inserts creates and
  revises or deletes with `only_creator=AGENT, only_pending=True`. An unknown or
  non-editable handle rolls back the attempt and raises `ModelRetry`
  (pydantic-ai reports it on the output tool's return part); otherwise the
  writes commit with the task. Withdraw deletes the row.
- "The agent's own" conventions means any agent run's: rows carry only
  `creator_type=AGENT`.

Tested only against FunctionModel ([test_conventions_agent.py](../../backend/tests/memory/test_conventions_agent.py),
[output](../../backend/tests/memory/test_conventions_agent_output.py),
[context](../../backend/tests/memory/test_conventions_context.py)).

## Observed behavior

Working prompt guidance (2026-11-08), motivated by the conventions snapshots and
the five pending rules in the local chapter-1–50 trial, is implemented in
`CONVENTIONS_INSTRUCTIONS` and the conventions toolset instructions:

- A coherent shared decision may cover a closed family; unseen members are not
  required. Normally use two or three examples, with complete short ladders
  allowed when their structure matters. New terms should not cause example-list
  growth when they already fit an existing rule.
- Preserve consistent established renderings unless a specific semantic error
  or inconsistency motivates change. Separate evidence from editorial choice;
  suffix matching alone does not establish shared meaning in every occurrence.
- Preserve the source's name/alias choice and identity disclosure. Definitions
  and aliases do not establish prose voice or dialogue register. Avoid style
  claims requiring source excerpts the agent cannot read.

These are provisional guidance, not a demonstrated quality improvement or a
fixed global convention/example budget. The motivating DB trial used
`deepseek:deepseek-v4-flash-low`, had no canonical term mappings at review time,
and included an overly prescriptive transformed-form naming rule. A fresh live
comparison is still needed; existing editable conventions may correctly remain
unchanged when a rerun supplies no new evidence.

One trial (2026-11-03, environment-specific group
`40c9245c-e452-4a68-99e3-63c250ced001`, chapters 1–49 of 下班，然后变成魔法少女,
`deepseek-v4-flash-low`, hand-written conventions informed by
[naming observations](naming-observations.md)) re-recorded and re-named every
chapter, so recording variance is mixed into the comparison:

- Targeted families became consistent (codenames such as 白玫 → White Rose,
  樱 → Sakura; 种级 → Seed-rank), and the agent extended the rank pattern to an
  unmentioned 卵/蠖/蛹 ladder.
- Broad rules apply broadly (e.g. 卵阶 and 卵级 both became Egg-rank).
  Unconstrained morphemes still varied (魔力 as Mana and Magic in one run).
- The recorder never created 国度 as a term, so the abbreviation rule had nothing
  to act on.

This shows the agent follows conventions; it does not measure quality. A cleaner
comparison runs naming-only jobs on one recorded group with conventions on and
off.
