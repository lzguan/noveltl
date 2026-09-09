from typing import Annotated, Literal, get_args

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.schemas import AgentModel
from src.memory.types import MemoryType, Scope

type GenderFactAspect = Literal["body", "identity", "presentation", "change_rule"]
GENDER_FACT_ASPECTS: tuple[GenderFactAspect, ...] = get_args(GenderFactAspect.__value__)
GENDER_FACT_MARKS: dict[GenderFactAspect, str] = {
    "body": "gender.body",
    "identity": "gender.identity",
    "presentation": "gender.presentation",
    "change_rule": "gender.change_rule",
}


class AdvancedGenderState(AgentModel):
    """Active, independently maintained gender state for one person."""

    body: list[AgentGlossaryMemory[str]] = Field(
        description="Active memories about the person's current physical sex or gendered body state."
    )
    identity: list[AgentGlossaryMemory[str]] = Field(
        description="Active memories about the person's own established gender identity."
    )
    presentation: list[AgentGlossaryMemory[str]] = Field(
        description="Active memories about how the person intentionally presents as themself."
    )
    change_rule: list[AgentGlossaryMemory[str]] = Field(
        description="Active durable rules governing the person's gender-related changes."
    )


GLOSSARY_ADVANCED_GENDER_FACT_READ_INSTRUCTIONS = """
Use `gender_state` only for one exact recurring person after forming a concrete
gender-state candidate or when another enabled toolset requires the person's
existing gender state. It returns body, identity, presentation, and change
rules separately. An empty aspect has no recorded state. More than one result
for body, identity, or presentation indicates conflicting data; do not add
another memory to that aspect. Multiple independent change rules may coexist.
""".strip()

GLOSSARY_ADVANCED_GENDER_FACT_WRITE_INSTRUCTIONS = """
FACT DEFINITION: A gender fact is a concise durable state or rule that remains
useful outside the bounded occurrence that established or demonstrated it.
It answers "What state or rule should later chapters know?" rather than "What
happened in this scene?" THIS TOOLSET MUST NOT RECORD EVENTS.

Maintain these independent aspects for recurring `person` terms:
- `body`: the person's currently embodied physical sex or gendered body state.
- `identity`: the person's own explicitly established gender identity.
- `presentation`: how the person intentionally presents as themself, excluding
  an assumed disguise, cover identity, role, or persona.
- `change_rule`: a durable ability, involuntary condition, constraint, trigger,
  or mechanic governing changes to gendered body state or presentation.

Semantic fact examples:
- `body`: `林玥's current body is female.`
- `identity`: `林玥 self-identifies as male.`
- `presentation`: `林玥 ordinarily presents as a woman when acting as themself.`
- `change_rule`: `林玥 changes into a female body whenever moonlight touches
  the amulet.`
- After a lasting bodily transformation, the fact records only the resulting
  current body. It does not include the former body, cause, chapter, ritual, or
  act of transformation.
- After a reveal, create or correct a fact only if the reveal establishes the
  person's actual current body or self-identity. Another person's belief is not
  the subject's fact.

Gender-related transformation capabilities and their intrinsic restrictions
belong in `change_rule`, including involuntary triggers and inability to choose
a resulting form. Do not duplicate the same mechanic in generic `ability` or
`limitation` facts. An independent non-gender capability remains a generic fact.
An artifact's intrinsic transformation function belongs in its definition;
record a character change rule only for independently useful character-specific
conditions, access, or constraints. Do not copy the artifact's whole definition.
Before writing such a rule, use `character_state_memories` when available to
check existing representations and all relevant pages. A related memory outside this writer's scope is not yours
to supersede; do not create a duplicate merely to change its category.

Keep identifying hair/eye features, markings, stature, anatomy, apparent age,
and recurring attire in the appearance writer when eligible. Gender facts do not inventory these
features or clothing. `presentation` records only explicitly established gender
presentation as oneself, not outfits or appearance-based guesses. Do not infer
body or self-identity from those descriptions.

Not facts: `林玥 was transformed into a woman during the eclipse` is an event;
`林玥 is posing as Lady Shen to enter the banquet` belongs to a disguise toolset
when one is provided and must otherwise be ignored; `沈秋 believes 林玥 is a
woman` is a perception relation; and `林玥 is attracted to 沈秋` concerns a
relationship or feeling. A person who is wrongly perceived as another gender
may still have independently established body, identity, or presentation
facts. Never replace those facts with the observer's belief. Do not infer body
or identity from names, clothing, appearance, occupation, attraction, social
role, stereotypes, pronouns alone, or another character's belief.

Body, identity, and presentation each permit one active memory per person.
Multiple independent change rules may coexist. Before every write, call
`character_state_memories` for the exact person unless that term was created in the current
run. Make no write if the same state or rule is already represented. Supersede
only the same aspect and tracked claim when it receives a replacement value.
For a change rule, supersede only the particular rule being corrected or
replaced; do not replace unrelated rules. Write the state or reusable rule, not
the transformation, discovery, evidence, reaction, or history that established
it. Expire a state or rule only when it explicitly stops being true without a
replacement; absence is not evidence.

Body, identity, and presentation may differ and remain simultaneously active.
A character may have no established canonical identity or may change it often;
record only what the source establishes and supersede chapter by chapter when
the current value changes. A temporary form does not replace a canonical body
unless it is the person's currently embodied body and the distinction matters
for continuity. Adaptation, comfort, distress, and sexual or romantic
attraction do not themselves change identity. Another character's perception
is not the subject's identity or presentation.

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
    """Retrieve active gender states and change rules for one exact person term."""
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
        presentation=[row for row in agent_page.rows if row.memory.mark == GENDER_FACT_MARKS["presentation"]],
        change_rule=[row for row in agent_page.rows if row.memory.mark == GENDER_FACT_MARKS["change_rule"]],
    )


def new_gender_fact_memory(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    aspect: GenderFactAspect,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Create one missing gender state or independent change rule for one person."""
    mark = _mark(aspect)
    if aspect != "change_rule":
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
                f"{term_name} already has an active {aspect} memory. Call character_state_memories and either leave it "
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
    """Replace one gender state or one particular change rule."""
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
    """Expire a gender state or change rule that explicitly stopped being true."""
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
