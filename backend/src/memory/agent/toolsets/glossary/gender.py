from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

GENDER_MARK = "gender"

GLOSSARY_GENDER_READ_INSTRUCTIONS = """
Retrieve gender memories only after forming one specific candidate about a
recurring person. Query one exact person term. Use `term_search` only for a
literal, case-insensitive substring expected in the memory text. Filters apply
before pagination and results are newest-first. Request another page only when
the filtered count requires it. A term created in the current run has no gender
history to retrieve.
""".strip()

GLOSSARY_GENDER_WRITE_INSTRUCTIONS = """
Maintain explicitly established gender-related state for recurring `person`
terms. THIS TOOLSET MUST NOT RECORD EVENTS. Preserve current gender even when
it seems mundane, because forgetting it can cause pronoun and other translation
errors. Treat unambiguous narration, self-identification, or a direct statement
as evidence. Do not infer gender from a name, clothing, appearance, occupation,
social role, or stereotype alone.

Store a short plain statement describing the exact established attribute. Do
not create repeated memories for pronouns or restatements. If the source
distinguishes gender identity, physical sex, or presentation, state the exact
attribute rather than collapsing them into one vague claim. Independent
attributes may coexist.

Before each write, use `gender_memories` to inspect the exact person's existing
gender state unless the term was created in the current run. Make no write when
the claim is already represented. Supersede only when the same attribute has a
replacement current value, and record the new value rather than an account of
the change. Pass the replacement's exact primary `term_name`; it may be a new
recurring name only when an alias relation establishes that both names identify
the same person. Expire a memory only when its exact attribute explicitly stops
being true without replacement. Absence is never evidence for expiry, and
approved memories change only on clear textual evidence.
""".strip()


def gender_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active gender memories for one exact person term."""
    return common.term_memories(ctx, term_name, MemoryType.FACT, GENDER_MARK, skip, limit, term_search)


def new_gender_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1, max_length=1)],
    scope: Scope | None = None,
) -> str:
    """Create a gender memory for one exact person term."""
    return common.create_memory(
        ctx,
        common.strip_marker(content, GENDER_MARK),
        term_names,
        MemoryType.FACT,
        scope,
        "new_gender_memory",
        GENDER_MARK,
    )


def supersede_gender_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    term_name: Annotated[str, Field(min_length=1)],
    scope: Scope | None = None,
) -> str:
    """Supersede a gender memory and associate its replacement with one exact person term."""
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, GENDER_MARK),
        MemoryType.FACT,
        scope,
        GENDER_MARK,
        replacement_term_names=[term_name],
        expected_marks=[GENDER_MARK],
    )


def expire_gender_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire a gender memory whose exact attribute explicitly stopped being true."""
    return common.expire_memory(ctx, memory_id, [MemoryType.FACT], marks=[GENDER_MARK])


glossary_gender_read_toolset = FunctionToolset(
    tools=[gender_memories],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_GENDER_READ_INSTRUCTIONS],
    sequential=True,
)

glossary_gender_write_toolset = FunctionToolset(
    tools=[new_gender_memory, supersede_gender_memory, expire_gender_memory],
    instructions=[GLOSSARY_GENDER_WRITE_INSTRUCTIONS],
    sequential=True,
)
