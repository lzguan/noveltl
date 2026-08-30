from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

type RelationCategory = Literal[
    "alias",
    "kinship",
    "friendship",
    "romance",
    "mentorship",
    "rank",
    "membership",
    "service",
    "ownership",
    "alliance",
    "rivalry",
    "organizational_hierarchy",
    "commercial_partnership",
]

GLOSSARY_RELATION_INSTRUCTIONS = """
Maintain explicit, continuity-relevant relationships between glossary terms.
THIS TOOLSET MUST NOT RECORD EVENTS. Do not record co-occurrence, temporary
cooperation, ordinary transactions, actions, location, vague enmity, or shared
participation in an occurrence as relations.

Associate every participant and select exactly one category: `alias` for terms
naming the same identity; `kinship`; explicitly established `friendship` or
`romance`; `mentorship`; durable `rank`, `membership`, `service`, or
`ownership`; an ongoing formal `alliance` or explicit `rivalry`;
`organizational_hierarchy`; or an ongoing `commercial_partnership` rather than
a one-time transaction. Friendship and romance may coexist unless the source
explicitly ends one.

Before writing, call `relation_memories` on one existing participant most
likely to reveal the candidate relation, with its one matching category. Form
the candidate before retrieval. Use `term_search` only for a literal,
case-insensitive substring expected in the memory text. Filters apply before
pagination and results are newest-first. Request another page only when the
filtered count requires it. Skip retrieval only when every participant is new.

Make no write when the relationship is already represented. Supersede a
relation only when the same relationship receives a replacement current value.
Expire it only when the chapter explicitly ends it without replacement.
Absence is never evidence for expiry. Complementary relations remain separate,
and approved memories change only on clear textual evidence.

For the shared lifecycle decision, the tracked claim is the particular
relationship between its participants, not every relation returned for one
participant or category. Different memberships, possessions, relatives, or
other compatible relationships may coexist. Treat aliases that express the
same identity equivalence as the same claim even when they use another known
name for that identity.
""".strip()


def relation_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    category: RelationCategory,
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active relations in one category for one exact glossary term."""
    return glossary_common.term_memories(ctx, term_name, MemoryType.RELATION, category, skip, limit, term_search)


def new_relation_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=2)],
    category: RelationCategory,
    scope: Scope | None = None,
) -> str:
    """Create a categorized relation between exact glossary terms."""
    return glossary_common.create_memory(
        ctx,
        glossary_common.strip_marker(content, category),
        term_names,
        MemoryType.RELATION,
        scope,
        "new_relation_memory",
        category,
    )


def supersede_relation_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    category: RelationCategory,
    scope: Scope | None = None,
) -> str:
    """Supersede an active relation with one categorized replacement."""
    return glossary_common.supersede_memory(
        ctx,
        memory_id,
        glossary_common.strip_marker(content, category),
        MemoryType.RELATION,
        scope,
        category,
    )


def expire_relation_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active relation that explicitly stopped being true."""
    return glossary_common.expire_memory(ctx, memory_id, [MemoryType.RELATION])


glossary_relation_toolset = FunctionToolset(
    tools=[
        relation_memories,
        new_relation_memory,
        supersede_relation_memory,
        expire_relation_memory,
    ],
    instructions=[GLOSSARY_RELATION_INSTRUCTIONS],
    sequential=True,
)
