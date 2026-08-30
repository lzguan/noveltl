from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

type FactCategory = Literal[
    "gender",
    "age_stage",
    "species",
    "appearance",
    "cultivation_level",
    "trait",
    "ability",
    "limitation",
]

GLOSSARY_FACT_INSTRUCTIONS = """
Maintain explicitly stated, continuity-critical attributes of glossary terms.
THIS TOOLSET MUST NOT RECORD EVENTS. Facts must be extremely rare; most
chapters need no new facts, and an ordinary chapter should receive no more than
two. Record a fact only when forgetting it could cause a later translation or
continuity error.

Each fact has one primary term and exactly one category: explicit `gender`;
explicit `age_stage`; `species`; stable identifying `appearance`; the current
canonical `cultivation_level`; an enduring inherent `trait`; an enduring
unusual `ability`; or an enduring `limitation`. Never record actions, history,
personality, emotions, intentions, discoveries, knowledge, location, inventory,
wealth, occupation, affiliation, ownership, routines, temporary state,
ordinary technique use, one-off feats, fatigue, pain, or temporary injury.

Multiple independent facts may share a category. Form one candidate before
calling `fact_memories`, then retrieve its exact primary term and one matching
category. Use `term_search` only for a literal, case-insensitive substring
expected in the memory text. Filters apply before pagination and results are
newest-first. Request another page only when the filtered count requires it.
Skip retrieval for a term created in the current run.

Write only a short plain statement in `content`; the category is stored
separately. Make no write when the fact is already represented. Supersede only
when the same attribute receives a replacement current value, and record the
new current value rather than an account of the change. Expire a fact only when
it explicitly stops being true without replacement. Absence is never evidence
for expiry. Complementary facts remain separate, and approved memories change
only on clear textual evidence.

For the shared lifecycle decision, the tracked claim is the primary subject's
specific attribute, not the broad category alone: for example, current gender,
age stage, species, cultivation stage, one appearance feature, one inherent
trait, one capability, or one limitation. Supersede a previous value of that
attribute, but create a separate fact for a genuinely independent attribute in
the same category. A refinement or fuller description of the same capability
is not an independent ability.
""".strip()


def fact_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    category: FactCategory,
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active facts in one category for one exact glossary term."""
    return glossary_common.term_memories(ctx, term_name, MemoryType.FACT, category, skip, limit, term_search)


def new_fact_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1, max_length=1)],
    category: FactCategory,
    scope: Scope | None = None,
) -> str:
    """Create a categorized fact for one primary glossary term."""
    return glossary_common.create_memory(
        ctx,
        glossary_common.strip_marker(content, category),
        term_names,
        MemoryType.FACT,
        scope,
        "new_fact_memory",
        category,
    )


def supersede_fact_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    category: FactCategory,
    scope: Scope | None = None,
) -> str:
    """Supersede an active fact with one categorized replacement."""
    return glossary_common.supersede_memory(
        ctx,
        memory_id,
        glossary_common.strip_marker(content, category),
        MemoryType.FACT,
        scope,
        category,
    )


def expire_fact_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active fact that explicitly stopped being true."""
    return glossary_common.expire_memory(ctx, memory_id, [MemoryType.FACT])


glossary_fact_toolset = FunctionToolset(
    tools=[fact_memories, new_fact_memory, supersede_fact_memory, expire_fact_memory],
    instructions=[GLOSSARY_FACT_INSTRUCTIONS],
    sequential=True,
)
