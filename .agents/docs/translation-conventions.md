# Translation conventions

Novel-level guidance for one memory group's target language, written by users
(and, later, agents). Conventions are global rules, not per-term data or memories.

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
  membership. Examples belong in the rule text for now; an examples child table
  keyed by `convention_id` is the intended extension.
- Arc scoping (quick-transmigration worlds, infinite-flow instances) was
  considered and deferred to a future arc concept shared with the glossary; see
  [follow-ups](memory-workflow-followups.md).
- `access.py` sits beneath both the user service and future agent toolsets and
  applies no caller policy. The service scopes statements with the
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
and the instructions are unchanged. Style conventions have no consumer yet.

## Observed behavior

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
