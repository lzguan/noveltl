from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

GENDER_PERCEPTION_MARK = "gender.perception"

GLOSSARY_ADVANCED_GENDER_RELATION_READ_INSTRUCTIONS = """
Use `gender_perception_memories` after forming a concrete candidate about how
one exact recurring observer or group perceives another person's gender. Query
the observer named in the candidate. When needed, use `subject_name_search`
only for a literal, case-insensitive source-language subject name expected in
the memory text. Results are active and newest-first. Request another page only
when the filtered count requires it.
""".strip()

GLOSSARY_ADVANCED_GENDER_RELATION_WRITE_INSTRUCTIONS = """
PERCEPTION RELATION DEFINITION: A gender perception is one observer's or
group's current belief about another person's gender. It is directional and
answers "How does this observer perceive this subject?" It does not establish
the subject's actual body, identity, or presentation. THIS TOOLSET MUST NOT
RECORD EVENTS.

Write one short statement in the form `Observer perceives Subject as ...` and
associate exactly that observer and subject. The perception may be mistaken;
incorrectly perceived gender still belongs in this toolset and must not
overwrite the subject's facts. Do not store self-perception here. A person's
own established view belongs to identity or presentation facts.

Use this toolset only while the subject appears as themself. Perception of an
explicit disguise, cover identity, assumed persona, or unnamed disguised role
belongs to a disguise toolset when one is provided, even when the disguise
changes perceived gender. Otherwise ignore it. Do not silently convert such a
perception into a fact about the person.

Before every write, call `gender_perception_memories` for the exact observer
and candidate subject unless both terms were created in the current run. Make
no write if the same perception is already represented. Supersede only when
the same observer's perception of the same subject receives a replacement
value. Expire it only when that perception explicitly ends without replacement;
absence is not evidence. Different observers' beliefs remain separate.
""".strip()


def gender_perception_memories(
    ctx: RunContext[MemAgentDeps],
    observer_term_name: Annotated[str, Field(min_length=1)],
    subject_name_search: Annotated[str | None, Field(min_length=1)] = None,
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active gender perceptions held by one exact observer term."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [observer_term_name],
        [MemoryType.RELATION],
        skip,
        limit,
        marks=[GENDER_PERCEPTION_MARK],
        term_search=subject_name_search,
    )
    return common.to_agent_memory_page(ctx, page)


def _validate_participants(observer_term_name: str, subject_term_name: str) -> None:
    if observer_term_name == subject_term_name:
        raise ModelRetry(
            "Observer and subject must differ. Store the person's own established view as an identity "
            "or presentation fact instead of a perception relation."
        )


def new_gender_perception_memory(
    ctx: RunContext[MemAgentDeps],
    observer_term_name: Annotated[str, Field(min_length=1)],
    subject_term_name: Annotated[str, Field(min_length=1)],
    content: str,
    scope: Scope | None = None,
) -> str:
    """Create one observer-to-subject gender perception relation."""
    _validate_participants(observer_term_name, subject_term_name)
    return common.create_memory(
        ctx,
        common.strip_marker(content, GENDER_PERCEPTION_MARK),
        [observer_term_name, subject_term_name],
        MemoryType.RELATION,
        scope,
        "new_gender_perception_memory",
        GENDER_PERCEPTION_MARK,
    )


def supersede_gender_perception_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    observer_term_name: Annotated[str, Field(min_length=1)],
    subject_term_name: Annotated[str, Field(min_length=1)],
    content: str,
    scope: Scope | None = None,
) -> str:
    """Replace one observer's perception of one subject."""
    _validate_participants(observer_term_name, subject_term_name)
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, GENDER_PERCEPTION_MARK),
        MemoryType.RELATION,
        scope,
        GENDER_PERCEPTION_MARK,
        replacement_term_names=[observer_term_name, subject_term_name],
        expected_marks=[GENDER_PERCEPTION_MARK],
    )


def expire_gender_perception_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire one gender perception that explicitly stopped being held."""
    return common.expire_memory(
        ctx,
        memory_id,
        [MemoryType.RELATION],
        marks=[GENDER_PERCEPTION_MARK],
    )


glossary_gender_advanced_relations_read_toolset = FunctionToolset(
    tools=[gender_perception_memories],
    instructions=[
        common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS,
        GLOSSARY_ADVANCED_GENDER_RELATION_READ_INSTRUCTIONS,
    ],
    sequential=True,
)

glossary_gender_advanced_relations_write_toolset = FunctionToolset(
    tools=[
        new_gender_perception_memory,
        supersede_gender_perception_memory,
        expire_gender_perception_memory,
    ],
    instructions=[GLOSSARY_ADVANCED_GENDER_RELATION_WRITE_INSTRUCTIONS],
    sequential=True,
)
