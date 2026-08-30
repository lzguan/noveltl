from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

GLOSSARY_DEFINITION_INSTRUCTIONS = """
Maintain canonical definitions for glossary terms. THIS TOOLSET MUST NOT RECORD
EVENTS. Never store actions, scene history, relationships, ownership, current
state, or biographies as definitions.

A definition is the intrinsic identity or meaning of exactly one term. It is
normally appropriate only for a `technique`, `item`, `concept`, `title`, or
`species` when the chapter states stable intrinsic meaning that will help later
translation. An `organization`, `place`, or `other` term may receive a
definition only when its stable nature or function is not evident from the
term itself. Never define a `person`, and never invent a definition merely to
accompany a new term.

Form one concrete candidate before calling `definition_memories`. Retrieve one
exact term and use `term_search` only for a literal, case-insensitive substring
that should occur in the memory text. Filters apply before pagination and
results are newest-first. Request another page only when the filtered count
requires it. Skip retrieval for a term created in the current run.

Maintain at most one active canonical definition per term. Make no write when
the meaning is already represented. Use `supersede_definition_memory` when the
chapter materially corrects or completes the existing definition, and
`expire_definition_memory` only when it explicitly stops being true without a
replacement. Absence is never evidence for expiry. Do not change an approved
memory without clear textual evidence.
""".strip()


def definition_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active definitions for one exact glossary term."""
    return glossary_common.term_memories(ctx, term_name, MemoryType.DEFINITION, None, skip, limit, term_search)


def new_definition_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1, max_length=1)],
    scope: Scope | None = None,
) -> str:
    """Create an unmarked definition for one exact glossary term."""
    return glossary_common.create_memory(
        ctx, content, term_names, MemoryType.DEFINITION, scope, "new_definition_memory"
    )


def supersede_definition_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Supersede an active definition from an earlier chapter."""
    return glossary_common.supersede_memory(ctx, memory_id, content, MemoryType.DEFINITION, scope)


def expire_definition_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active definition that explicitly stopped being true."""
    return glossary_common.expire_memory(ctx, memory_id, [MemoryType.DEFINITION])


glossary_definition_toolset = FunctionToolset(
    tools=[
        definition_memories,
        new_definition_memory,
        supersede_definition_memory,
        expire_definition_memory,
    ],
    instructions=[GLOSSARY_DEFINITION_INSTRUCTIONS],
    sequential=True,
)
