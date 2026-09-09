"""Directional impersonation state, never identity equivalence."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.types import MemoryType, Scope

IMPERSONATION_MARK = "impersonation"
IMPERSONATION_INSTRUCTIONS = """
Maintain active impersonation: an actor is posing as a different, independently
existing person. This is a directional relation, NOT an alias. An invented
persona or named transformed form belonging to the actor instead belongs to
alias.persona or alias.transformation when that writer is enabled. A spelling
variant is alias.spelling. Never link an impersonator and target as aliases.

Before writing, read character_state_memories for the actor and inspect the
impersonations section, paging it with impersonation_skip as needed. Each
record names the actor and target explicitly; association order has no meaning.
Create when the source establishes an ongoing impersonation, supersede when
its target or claim changes, and expire when it explicitly ends. Absence is
not expiry. Do not record hypothetical plans, anonymous masks, or every action
performed in disguise. The target's facts do not become the actor's facts.
This relation does not assert any observer is fooled or knows the truth.
Physical transformation mechanics remain independent gender change rules when
supported; disguising oneself does not exclude recording an actual transformation.
""".strip()


def _claim(actor: str, target: str, content: str) -> str:
    if actor == target:
        raise ModelRetry("Impersonation requires two distinct individuals, not the actor's own alias.")
    return f"{actor} is impersonating {target}. {content}"


def new_impersonation_memory(
    ctx: RunContext[MemAgentDeps],
    actor_term_name: Annotated[str, Field(min_length=1)],
    target_term_name: Annotated[str, Field(min_length=1)],
    content: str,
) -> str:
    """Record actor -> target state; content adds source-grounded context."""
    return common.create_memory(
        ctx,
        _claim(actor_term_name, target_term_name, content),
        [actor_term_name, target_term_name],
        MemoryType.RELATION,
        Scope.PERSIST,
        "new_impersonation_memory",
        IMPERSONATION_MARK,
    )


def supersede_impersonation_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    actor_term_name: Annotated[str, Field(min_length=1)],
    target_term_name: Annotated[str, Field(min_length=1)],
    content: str,
) -> str:
    """Replace an active impersonation with its complete directional claim."""
    return common.supersede_memory(
        ctx,
        memory_id,
        _claim(actor_term_name, target_term_name, content),
        MemoryType.RELATION,
        Scope.PERSIST,
        IMPERSONATION_MARK,
        replacement_term_names=[actor_term_name, target_term_name],
        expected_marks=[IMPERSONATION_MARK],
    )


def expire_impersonation_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """End an impersonation without ending either individual's identity."""
    return common.expire_memory(ctx, memory_id, [MemoryType.RELATION], marks=[IMPERSONATION_MARK])


glossary_impersonation_write_toolset = FunctionToolset(
    tools=[new_impersonation_memory, supersede_impersonation_memory, expire_impersonation_memory],
    instructions=[IMPERSONATION_INSTRUCTIONS],
    sequential=True,
)
