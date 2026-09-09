"""Scoped cultivation-state writes using the existing cultivation mark."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.agent.toolsets.glossary.guidance.cultivation import GLOSSARY_CULTIVATION_INSTRUCTIONS
from src.memory.types import MemoryType, Scope

CULTIVATION_MARK = "cultivation_level"
CULTIVATION_WRITE_INSTRUCTIONS = """
Maintain cultivation facts only for individual characters. Before each
candidate, use character_state_memories for that exact person unless newly
created. Compare the same cultivation track, not every level returned. Store
one track per memory, name that track in the content, and leave unchanged when
already represented. Supersede its previous completed level when it changes;
expire only when that track explicitly ends without replacement. Do not write
general abilities, gender rules, appearance, or system status with these tools.
Read visibility never grants permission to change other categories.
""".strip()


def new_cultivation_memory(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    content: str,
    scope: Scope | None = None,
) -> str:
    """Record a character's completed level on one named cultivation track."""
    return common.create_memory(
        ctx,
        content,
        [term_name],
        MemoryType.FACT,
        scope,
        "new_cultivation_memory",
        CULTIVATION_MARK,
    )


def supersede_cultivation_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    term_name: Annotated[str, Field(min_length=1)],
    content: str,
    scope: Scope | None = None,
) -> str:
    """Replace the previous level of the same cultivation track."""
    return common.supersede_memory(
        ctx,
        memory_id,
        content,
        MemoryType.FACT,
        scope,
        CULTIVATION_MARK,
        replacement_term_names=[term_name],
        expected_marks=[CULTIVATION_MARK],
    )


def expire_cultivation_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """End only a cultivation-level fact."""
    return common.expire_memory(ctx, memory_id, [MemoryType.FACT], marks=[CULTIVATION_MARK])


glossary_cultivation_write_toolset = FunctionToolset(
    tools=[new_cultivation_memory, supersede_cultivation_memory, expire_cultivation_memory],
    instructions=[GLOSSARY_CULTIVATION_INSTRUCTIONS, CULTIVATION_WRITE_INSTRUCTIONS],
    sequential=True,
)
