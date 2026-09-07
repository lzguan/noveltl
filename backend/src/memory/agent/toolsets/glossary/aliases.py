"""Scoped writer for identity aliases stored as glossary relation memories."""

from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary.access import ALIAS_MARK
from src.memory.types import MemoryType, Scope

GLOSSARY_ALIAS_WRITE_INSTRUCTIONS = """
Maintain explicit aliases: two distinct source-language terms that the text
establishes as the same identity, such as a name, title, codename, persona, or
disguise. This is identity equivalence, not a relationship, resemblance,
succession, shared role, or a temporary association. Do not merge, rename, or
otherwise alter either term or any existing fact; alias-aware readers retain
the original term forms and marks of every returned memory.

For example, 林昀 may be an adult man while 翠雀 is his magical-girl persona:
link them, but retain their distinct form-specific physical presentation
memories. A person merely changing out of a disguise does not end the alias.
If a source persona later becomes an independent person, expire the relevant
pair link on explicit textual evidence.

Before a candidate, use `relation_memories` with category `alias` for one
known form. Create exactly one pair when no active equivalent link exists.
Supersede only to correct or replace the same pair claim, passing the complete
replacement pair; expire only when the text explicitly ends or disproves the
identity claim. Expiring one pair removes only paths that require that link.
Absence is never evidence for expiry. This toolset must not record events or
ordinary relations.
""".strip()


def _distinct_pair(term_names: list[str]) -> None:
    if len(term_names) != 2 or len(set(term_names)) != 2:
        raise ModelRetry("An alias must contain two distinct exact glossary terms.")


def new_alias_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=2, max_length=2)],
) -> str:
    """Create one active pair alias without merging either term's memories."""
    _distinct_pair(term_names)
    return common.create_memory(
        ctx, content, term_names, MemoryType.RELATION, Scope.PERSIST, "new_alias_memory", ALIAS_MARK
    )


def supersede_alias_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    term_names: Annotated[list[str], Field(min_length=2, max_length=2)],
) -> str:
    """Replace one earlier pair alias with a corrected active pair alias."""
    _distinct_pair(term_names)
    return common.supersede_memory(
        ctx,
        memory_id,
        content,
        MemoryType.RELATION,
        Scope.PERSIST,
        ALIAS_MARK,
        replacement_term_names=term_names,
        expected_marks=[ALIAS_MARK],
    )


def expire_alias_memory(ctx: RunContext[MemAgentDeps], memory_id: str) -> str:
    """Expire one pair alias that explicitly stopped being true."""
    return common.expire_memory(ctx, memory_id, [MemoryType.RELATION], marks=[ALIAS_MARK])


glossary_aliases_write_toolset = FunctionToolset(
    tools=[new_alias_memory, supersede_alias_memory, expire_alias_memory],
    instructions=[GLOSSARY_ALIAS_WRITE_INSTRUCTIONS],
    sequential=True,
)
