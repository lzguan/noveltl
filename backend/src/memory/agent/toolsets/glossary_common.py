import json
from uuid import UUID

from pydantic_ai import ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.exceptions import GlossaryTermNotFoundException, MemoryNotFoundException
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.schemas import AgentMemory
from src.memory.types import Creator, MemoryType, Scope
from src.schemas import Page


def create_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: list[str],
    mem_type: MemoryType,
    scope: Scope | None,
    tool_name: str,
) -> str:
    """Create a glossary memory and translate its database UUID for the agent."""
    db = ctx.deps.db
    try:
        with db.begin_nested():
            new_memory, _ = access.create_memory(
                db,
                ctx.deps.mem_access_context,
                Creator.AGENT,
                mem_type,
                term_names,
                content,
                scope,
            )
    except GlossaryTermNotFoundException as exc:
        missing_term_names = access.get_missing_term_names(
            db,
            ctx.deps.mem_access_context.memory_group_id,
            term_names,
        )
        if missing_term_names:
            serialized_terms = json.dumps(missing_term_names, ensure_ascii=False)
            raise ModelRetry(
                f"Missing glossary terms: {serialized_terms}. Call add_term once for each missing exact term, "
                f"wait for those calls to succeed, then retry {tool_name} with the same content, scope, and "
                "complete term_names list. Do not retry before adding the missing terms."
            ) from exc
        raise ModelRetry(
            f"Every memory must reference at least one glossary term. Add the intended exact source term to "
            f"term_names, then retry {tool_name}."
        ) from exc
    return ctx.deps.uuid_cache.new(new_memory.memory_id)


def supersede_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    mem_type: MemoryType,
    scope: Scope | None,
) -> str:
    """Supersede a glossary memory and translate its database UUID for the agent."""
    try:
        current_id = ctx.deps.uuid_cache.get_uuid(memory_id)
    except KeyError as exc:
        raise ModelRetry(f"Memory {memory_id} not found.") from exc

    try:
        with ctx.deps.db.begin_nested():
            new_memory, _ = access.supersede_memory(
                ctx.deps.db,
                ctx.deps.mem_access_context,
                current_id,
                Creator.AGENT,
                mem_type,
                content,
                scope,
            )
    except MemoryNotFoundException as exc:
        raise ModelRetry(
            f"Memory {memory_id} does not exist, has already ended, or cannot be superseded in this chapter. "
            "Do not retry this memory handle. A memory created in the current chapter cannot be superseded; "
            "continue without changing it. For an older memory, retrieve its current handle before making a "
            "different call."
        ) from exc
    return ctx.deps.uuid_cache.new(new_memory.memory_id)


def expire_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    memory_types: list[MemoryType],
) -> str:
    """Expire a glossary memory without creating a replacement."""
    try:
        current_id = ctx.deps.uuid_cache.get_uuid(memory_id)
    except KeyError as exc:
        raise ModelRetry(f"Memory {memory_id} not found.") from exc

    try:
        with ctx.deps.db.begin_nested():
            access.expire_memory(
                ctx.deps.db,
                ctx.deps.mem_access_context,
                current_id,
                memory_types,
            )
    except MemoryNotFoundException as exc:
        raise ModelRetry(
            f"Memory {memory_id} does not exist, has already ended, has a type outside this toolset, or cannot "
            "be expired in this chapter. Do not retry this memory handle. A memory created in the current "
            "chapter cannot be expired; continue without changing it."
        ) from exc
    return f"Memory {memory_id} expired successfully."


def to_agent_memory_page(
    ctx: RunContext[MemAgentDeps],
    page: Page[AgentGlossaryMemory[UUID]],
) -> Page[AgentGlossaryMemory[str]]:
    """Translate database memory UUIDs in a page to short agent-facing handles."""
    return Page[AgentGlossaryMemory[str]](
        count=page.count,
        rows=[
            AgentGlossaryMemory[str](
                memory=AgentMemory[str].model_validate(
                    {
                        **glossary_memory.memory.model_dump(),
                        "memory_id": ctx.deps.uuid_cache.new(glossary_memory.memory.memory_id),
                    }
                ),
                terms=glossary_memory.terms,
            )
            for glossary_memory in page.rows
        ],
    )
