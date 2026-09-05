from typing import Annotated, Literal, get_args

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

type FactCategory = Literal[
    "age_stage",
    "species",
    "appearance",
    "cultivation_level",
    "ability",
    "limitation",
]
FACT_CATEGORIES: tuple[FactCategory, ...] = get_args(FactCategory.__value__)

GLOSSARY_FACT_READ_INSTRUCTIONS = """
Retrieve facts only after forming one specific candidate. Query its exact
primary term and the candidate's category. An `ability` or `limitation` query
returns both categories together, so a prior classification difference does
not hide a related claim. Inspect both kinds of result; do not repeat the same
query under the other category. All other categories retrieve only themselves.
Use `term_search` only for a literal,
case-insensitive substring expected in the memory text. Filters apply before
pagination and results are newest-first. Request another page only when the
filtered count requires it. A term created in the current run has no fact
history to retrieve.
""".strip()

GLOSSARY_FACT_WRITE_INSTRUCTIONS = """
Maintain explicitly stated, continuity-critical attributes of glossary terms.
THIS TOOLSET MUST NOT RECORD EVENTS. Facts must be extremely rare; most
chapters need no new generic facts. Record a fact only when forgetting it could
cause a later translation or continuity error. Gender is maintained by the
dedicated gender tools and must not be written with this toolset.

Each fact has one primary term and exactly one category: explicit `age_stage`;
`species`; stable identifying `appearance`; the current canonical
`cultivation_level`; an enduring unusual
`ability`; or an enduring `limitation`. Never record actions, history,
personality, emotions, intentions, discoveries, knowledge, location,
inventory, wealth, occupation, affiliation, ownership, routines, temporary
state, ordinary technique use, one-off feats, fatigue, pain, or temporary
injury.

Multiple independent facts may share a category.

An `ability` describes what the subject can do, including the conditions and
intrinsic limits needed to describe that capability accurately. A `limitation`
describes an enduring vulnerability, impairment, or restriction on the subject
that is not merely an operating condition of a recorded ability. Do not split
one capability into ability and limitation memories merely because part of its
description is negative. These distinctions do not relax the eligibility
rules above.

Examples:
- "林渊 can teleport only between marked locations." is one `ability`,
  including its constraint; do not separately record inability to teleport
  elsewhere.
- "林渊 cannot cultivate because his meridians are permanently damaged." is
  a `limitation`.
- "林渊 is vulnerable to silver regardless of which ability he uses." is a
  `limitation` independent of those abilities.
- "林渊 cannot teleport." is normally omitted when it is merely the ordinary
  absence of an ability; do not inventory everything a subject cannot do.

When a capability's range, conditions, or intrinsic restrictions change,
supersede the existing ability with its new complete current description. Do
not create a separate limitation for the changed restriction. For example,
learning to teleport to any visible location replaces the marked-location
ability above rather than adding an independent ability or limitation.

Write only a short plain statement in `content`; the category is stored
separately. Before acting on each candidate, call `fact_memories` as described
by the fact retrieval instructions, unless the term was created in the current
run. Make no write when the fact is already represented. Supersede only when
the same attribute receives a replacement current value, and record the new
current value rather than an account of the change. Pass the replacement's
exact primary `term_name` to `supersede_fact_memory`; this is normally the same
term, but it may be a new recurring name when an alias relation establishes
that both names identify the same person. Expire a fact only when it explicitly
stops being true without replacement. Absence is never evidence for expiry.
Complementary facts remain separate, and approved memories change only on
clear textual evidence.

For the shared lifecycle decision, the tracked claim is the primary subject's
specific attribute, not the broad category alone: for example, age stage,
species, cultivation stage, one appearance feature, one
capability, or one limitation. Supersede a previous value of that
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
    """Retrieve active facts for one exact term; ability and limitation share a result set."""
    marks = ["ability", "limitation"] if category in ("ability", "limitation") else [category]
    page = common.access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType.FACT],
        skip,
        limit,
        marks=marks,
        term_search=term_search,
    )
    return common.to_agent_memory_page(ctx, page)


def new_fact_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1, max_length=1)],
    category: FactCategory,
    scope: Scope | None = None,
) -> str:
    """Create a categorized fact for one primary glossary term."""
    return common.create_memory(
        ctx,
        common.strip_marker(content, category),
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
    term_name: Annotated[str, Field(min_length=1)],
    category: FactCategory,
    scope: Scope | None = None,
) -> str:
    """Supersede an active fact and associate its replacement with one exact primary term."""
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, category),
        MemoryType.FACT,
        scope,
        category,
        replacement_term_names=[term_name],
        expected_marks=list(FACT_CATEGORIES),
    )


def expire_fact_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active fact that explicitly stopped being true."""
    return common.expire_memory(ctx, memory_id, [MemoryType.FACT], marks=list(FACT_CATEGORIES))


glossary_facts_read_toolset = FunctionToolset(
    tools=[fact_memories],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_FACT_READ_INSTRUCTIONS],
    sequential=True,
)

glossary_facts_write_toolset = FunctionToolset(
    tools=[new_fact_memory, supersede_fact_memory, expire_fact_memory],
    instructions=[GLOSSARY_FACT_WRITE_INSTRUCTIONS],
    sequential=True,
)
