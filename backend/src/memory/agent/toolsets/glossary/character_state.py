"""Shared, read-only context for independently scoped character writers."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.agent.toolsets.glossary.appearance import APPEARANCE_MARKS
from src.memory.agent.toolsets.glossary.cultivation import CULTIVATION_MARK
from src.memory.agent.toolsets.glossary.facts import FACT_CATEGORIES
from src.memory.agent.toolsets.glossary.gender import GENDER_MARK
from src.memory.agent.toolsets.glossary.gender_advanced_facts import GENDER_FACT_MARKS
from src.memory.agent.toolsets.glossary.gender_advanced_relations import (
    GLOSSARY_ADVANCED_GENDER_RELATION_READ_INSTRUCTIONS,
    gender_perception_memories,
)
from src.memory.plugins.glossary.schemas import AgentGlossaryMemoryPage
from src.memory.types import MemoryType

CHARACTER_STATE_INSTRUCTIONS = """
Use `character_state_memories` before character-state writes. It reads core
attributes, physical appearance, attire, cultivation, and gender state together
even when their writers are disabled. A candidate can cross domain boundaries:
appearance versus gendered body/presentation, or ability/limitation versus a
gender change rule.
Do not infer permission to change a memory merely because it is returned.

Results retain their original marks and memory IDs. Related attributes are not
necessarily the same claim. Keep body, identity, appearance, and presentation
distinct. Legacy `gender` records retain their original wording; do not guess
an aspect for ambiguous legacy state. Observer beliefs and events are excluded;
use their readers when enabled.

Alias context links names without merging their stored state. In particular,
different physical forms or personas may have conflicting appearance or
presentation memories that must remain associated with their original terms.
Alias-derived context is not by itself evidence to write, supersede, or expire
any fact; corroborate the source and preserve the intended exact primary term.

Query one source form, inspect aliases alongside the returned count, and request
subsequent pages when relevant existing state has not been found and more rows
remain. Alias expansion follows active pair links transitively but is bounded;
when `aliases_truncated` is true, do not assume the returned component is
complete. Results retain each memory's original terms, are active, newest-first,
and bounded by limit; count covers the expanded matching set, not only this
page. Avoid a text filter when wording is uncertain. A literal `term_search`
narrows all included categories before pagination.
All character fact writers use this reader and enforce their own mutation scope.
Use gender_perception_memories for the separate directional observer query.
""".strip()


def character_state_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> AgentGlossaryMemoryPage[str]:
    """Read a bounded page of generic and gender facts, independent of enabled writers."""
    page = common.access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType.FACT],
        skip,
        limit,
        marks=[
            *FACT_CATEGORIES,
            "appearance",
            *APPEARANCE_MARKS.values(),
            CULTIVATION_MARK,
            GENDER_MARK,
            *GENDER_FACT_MARKS.values(),
        ],
        term_search=term_search,
        expand_aliases=True,
    )
    if not isinstance(page, AgentGlossaryMemoryPage):
        raise RuntimeError("Character state retrieval must preserve alias context")
    return common.to_agent_alias_memory_page(ctx, page)


glossary_character_state_read_toolset = FunctionToolset(
    tools=[character_state_memories, gender_perception_memories],
    instructions=[
        common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS,
        CHARACTER_STATE_INSTRUCTIONS,
        GLOSSARY_ADVANCED_GENDER_RELATION_READ_INSTRUCTIONS,
    ],
    sequential=True,
)
