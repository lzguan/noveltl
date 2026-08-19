from uuid import UUID

from pydantic_ai import FunctionToolset, RunContext
from sqlalchemy import SQLColumnExpression

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.glossary.access import create_memory, create_term, get_terms_in_chapter, inspect_terms, supersede_memory
from src.memory.glossary.schemas import GlossaryMemory, GlossaryTerm
from src.memory.schemas import Memory
from src.memory.types import Creator, MemoryType, Scope


def contains_query(chapter: SQLColumnExpression[str], term: SQLColumnExpression[str]) -> SQLColumnExpression[bool]:
    """Return a SQL expression that evaluates to true if the chapter contains the term."""
    return chapter.contains(term)


def terms_in_chapter(ctx: RunContext[MemAgentDeps]) -> list[GlossaryTerm]:
    """See all glossary terms occurring in the exact chapter content pinned by the context."""
    with ctx.deps.db_factory() as db:
        terms = get_terms_in_chapter(db, ctx.deps.mem_access_context, contains_query)
        return [GlossaryTerm.model_validate(term) for term in terms]


def term_memories(ctx: RunContext[MemAgentDeps], term_names: list[str]) -> list[GlossaryMemory]:
    """See all memories associated with a list of glossary terms in the current context."""
    with ctx.deps.db_factory() as db:
        memories = inspect_terms(db, ctx.deps.mem_access_context, term_names)
        return [
            GlossaryMemory(
                memory=Memory.model_validate(memory), terms=[GlossaryTerm.model_validate(term) for term in terms]
            )
            for memory, terms in memories
        ]


def add_term(ctx: RunContext[MemAgentDeps], term_name: str) -> UUID:
    """Add a new glossary term to the current memory group."""
    with ctx.deps.db_factory() as db:
        new_term = create_term(db, ctx.deps.mem_access_context.memory_group_id, term_name)
        db.commit()
        return new_term.term_id


def new_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: list[str],
    mem_type: MemoryType,
    scope: Scope | None = None,
) -> UUID:
    """Create a new memory and associate it with a list of glossary terms in the current context."""
    with ctx.deps.db_factory() as db:
        new_mem, assocs = create_memory(
            db, ctx.deps.mem_access_context, Creator.AGENT, mem_type, term_names, content, scope
        )
        new_id = new_mem.memory_id
        db.commit()
    return new_id


def rewrite_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: UUID,
    content: str,
    mem_type: MemoryType,
    scope: Scope | None = None,
) -> UUID:
    """Supersede an existing memory in the current context. Use this to update outdated or incorrect information in a memory."""
    with ctx.deps.db_factory() as db:
        new_mem, assocs = supersede_memory(
            db, ctx.deps.mem_access_context, memory_id, Creator.AGENT, mem_type, content, scope
        )
        new_id = new_mem.memory_id
        db.commit()
    return new_id


glossary_toolset = FunctionToolset(
    tools=[terms_in_chapter, term_memories, add_term, new_memory, rewrite_memory],
    instructions="Use these tools to manage glossary terms and memories relating to glossary terms. You can see all glossary terms in the current chapter, inspect memories associated with specific terms, add new terms, and create or supersede memories for existing terms.",
)
