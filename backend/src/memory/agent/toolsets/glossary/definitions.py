from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

GLOSSARY_DEFINITION_READ_INSTRUCTIONS = """
Retrieve definitions only after forming one concrete candidate. Query one exact
term and use `term_search` only for a literal, case-insensitive substring that
should occur in the memory text. Filters apply before pagination and results
are newest-first. Request another page only when the filtered count requires
it. A term created in the current run has no definition history to retrieve.
""".strip()

GLOSSARY_DEFINITION_WRITE_INSTRUCTIONS = """
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

Definitions own a named object's or technique's intrinsic function and its
operating constraints. Generic facts describe an individual character's
attributes or particular access to a capability, not an object's specification.
For example, "月镜 allows its wielder to teleport between marked locations"
defines the item; "林渊 alone can activate 月镜" may warrant a character ability
when forgetting that access would cause a continuity error. Do not repeat the
item's full definition as a character fact. An individual's species belongs in
a character fact; the intrinsic nature of that species belongs in its definition.
A broken object's temporary condition is current state, not its definition.

Maintain at most one active canonical definition per term. Make no write when
the meaning is already represented. Before acting on each candidate, call
`definition_memories` as described by the definition retrieval instructions,
unless the term was created in the current run. Use
`supersede_definition_memory` when the chapter materially corrects or completes
the existing definition, and `expire_definition_memory` only when it explicitly
stops being true without a replacement. Absence is never evidence for expiry.
Do not change an approved memory without clear textual evidence.

For the shared lifecycle decision, the tracked claim is the exact term's one
canonical meaning. If an active definition exists, an eligible candidate for
that term must result in no write, supersession, or expiry—never a second active
definition.
""".strip()


def definition_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    term_search: Annotated[str | None, Field(min_length=1)] = None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve active definitions for one exact glossary term."""
    return common.term_memories(ctx, term_name, MemoryType.DEFINITION, None, skip, limit, term_search)


def new_definition_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1, max_length=1)],
    scope: Scope | None = None,
) -> str:
    """Create an unmarked definition for one exact glossary term."""
    return common.create_memory(ctx, content, term_names, MemoryType.DEFINITION, scope, "new_definition_memory")


def supersede_definition_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Supersede an active definition from an earlier chapter."""
    return common.supersede_memory(
        ctx,
        memory_id,
        content,
        MemoryType.DEFINITION,
        scope,
        expected_marks=[None],
    )


def expire_definition_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire an active definition that explicitly stopped being true."""
    return common.expire_memory(ctx, memory_id, [MemoryType.DEFINITION], marks=[None])


glossary_definitions_read_toolset = FunctionToolset(
    tools=[definition_memories],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_DEFINITION_READ_INSTRUCTIONS],
    sequential=True,
)

glossary_definitions_write_toolset = FunctionToolset(
    tools=[new_definition_memory, supersede_definition_memory, expire_definition_memory],
    instructions=[GLOSSARY_DEFINITION_WRITE_INSTRUCTIONS],
    sequential=True,
)
