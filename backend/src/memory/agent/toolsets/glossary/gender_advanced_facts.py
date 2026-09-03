from typing import Annotated, Literal, get_args

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.schemas import AgentModel
from src.memory.types import MemoryType, Scope

type GenderFactAspect = Literal["body", "identity"]
GENDER_FACT_ASPECTS: tuple[GenderFactAspect, ...] = get_args(GenderFactAspect.__value__)
GENDER_FACT_MARKS: dict[GenderFactAspect, str] = {
    "body": "gender.body",
    "identity": "gender.identity",
}


class AdvancedGenderState(AgentModel):
    """Active, independently maintained gender state for one person."""

    body: list[AgentGlossaryMemory[str]] = Field(
        description="Active memories about the person's current physical sex or gendered body state."
    )
    identity: list[AgentGlossaryMemory[str]] = Field(
        description="Active memories about the person's own established gender identity."
    )


GLOSSARY_ADVANCED_GENDER_FACT_READ_INSTRUCTIONS = """
Use `gender_state` only for one exact recurring person after forming a concrete
gender-state candidate or when another enabled toolset requires the person's
existing gender state. It returns physical body state and self-identity
separately. An empty aspect has no recorded state. More than one result in an
aspect indicates conflicting existing data; do not add another memory to that
aspect.
""".strip()

GLOSSARY_ADVANCED_GENDER_FACT_WRITE_INSTRUCTIONS = """
FACT DEFINITION: A gender fact is a concise statement of an attribute that is
true for the person now and is expected to remain useful in later chapters
without recounting how it became true. It answers "What is currently true?"
rather than "What happened?" Maintain two independent current attributes for
recurring `person` terms: `body` is the person's current physical sex or
gendered body state; `identity` is the person's own explicitly established
gender identity. THIS TOOLSET MUST NOT RECORD EVENTS.

Semantic fact examples:
- `body`: `林玥's current body is female.`
- `identity`: `林玥 self-identifies as male.`
- After a lasting bodily transformation, the fact records only the resulting
  current body. It does not include the former body, cause, chapter, ritual, or
  act of transformation.
- After a reveal, create or correct a fact only if the reveal establishes the
  person's actual current body or self-identity. Another person's belief is not
  the subject's fact.

Not facts: `林玥 was transformed into a woman during the eclipse` is an event;
`林玥 is pretending to be a woman at the banquet` is a temporary presentation;
and `林玥 is attracted to 沈秋` concerns a relationship or feeling. Do not infer
body or identity from names, clothing, appearance, occupation, attraction,
social role, stereotypes, pronouns alone, or another character's belief.

Each aspect permits one active memory per person. Before every write, call
`gender_state` for the exact person unless that term was created in the current
run. Make no write if the aspect is already represented. Supersede the existing
memory only when the same aspect has a replacement current value. Never
supersede one aspect with the other. Write a short statement of current state,
not the transformation, discovery, evidence, pronouns, reaction, attraction,
or history that established it. Expire an aspect only when it explicitly stops
being true without replacement; absence is not evidence.

Body and identity may differ and remain simultaneously active. A temporary
form or disguise does not replace canonical body state. Adaptation, comfort,
distress, presentation, and sexual or romantic attraction do not themselves
change identity. Another character's perception is not the subject's identity.

A changed fact does not automatically justify an event memory. When advanced
gender event tools are enabled, record both only if the resulting current state
and the occurrence that caused or revealed it are independently important for
later continuity. The fact contains only the current attribute; the event
contains only the consequential occurrence and its immediate outcome.
""".strip()


def _mark(aspect: GenderFactAspect) -> str:
    return GENDER_FACT_MARKS[aspect]


def gender_state(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
) -> AdvancedGenderState:
    """Retrieve active body and identity memories for one exact person term."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType.FACT],
        0,
        20,
        marks=list(GENDER_FACT_MARKS.values()),
    )
    agent_page = common.to_agent_memory_page(ctx, page)
    return AdvancedGenderState(
        body=[row for row in agent_page.rows if row.memory.mark == GENDER_FACT_MARKS["body"]],
        identity=[row for row in agent_page.rows if row.memory.mark == GENDER_FACT_MARKS["identity"]],
    )


def new_gender_fact_memory(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    aspect: GenderFactAspect,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Create one missing body or identity state for one exact person term."""
    mark = _mark(aspect)
    existing = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType.FACT],
        0,
        1,
        marks=[mark],
    )
    if existing.count:
        raise ModelRetry(
            f"{term_name} already has an active {aspect} memory. Call gender_state and either leave it "
            "unchanged or supersede its handle; do not create another memory for this aspect."
        )
    return common.create_memory(
        ctx,
        common.strip_marker(content, mark),
        [term_name],
        MemoryType.FACT,
        scope,
        "new_gender_fact_memory",
        mark,
    )


def supersede_gender_fact_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    term_name: Annotated[str, Field(min_length=1)],
    aspect: GenderFactAspect,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Replace the current value of one exact gender-state aspect."""
    mark = _mark(aspect)
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, mark),
        MemoryType.FACT,
        scope,
        mark,
        replacement_term_names=[term_name],
        expected_marks=[mark],
    )


def expire_gender_fact_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire a body or identity state that explicitly stopped being true."""
    return common.expire_memory(
        ctx,
        memory_id,
        [MemoryType.FACT],
        marks=list(GENDER_FACT_MARKS.values()),
    )


glossary_gender_advanced_facts_read_toolset = FunctionToolset(
    tools=[gender_state],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_ADVANCED_GENDER_FACT_READ_INSTRUCTIONS],
    sequential=True,
)

glossary_gender_advanced_facts_write_toolset = FunctionToolset(
    tools=[new_gender_fact_memory, supersede_gender_fact_memory, expire_gender_fact_memory],
    instructions=[GLOSSARY_ADVANCED_GENDER_FACT_WRITE_INSTRUCTIONS],
    sequential=True,
)
