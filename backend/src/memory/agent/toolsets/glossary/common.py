import json
from uuid import UUID

from pydantic_ai import ModelRetry, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.exceptions import GlossaryTermNotFoundException, MemoryNotFoundException
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryMemoryPage
from src.memory.schemas import AgentMemory
from src.memory.types import Creator, MemoryType, Scope
from src.schemas import Page

GLOSSARY_READ_SUPPORT_INSTRUCTIONS = """
These are retrieval support tools. Do not call them speculatively. Other
enabled tool instructions may require checking existing memories before
creating, superseding, expiring, or leaving a candidate unchanged. Follow
those instructions to decide when retrieval is required or may be skipped;
use the instructions below to construct the retrieval call.

Retrieval may also be used when the chapter explicitly refers to an earlier
state, relationship, definition, or continuing event that must be understood
to decide a concrete candidate's lifecycle, even if the chapter does not fully
restate that context. Do not retrieve merely to investigate unclear prose,
discover possible candidates, or gather general background.
""".strip()


def term_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: str,
    memory_type: MemoryType,
    mark: str | None,
    skip: int,
    limit: int,
    term_search: str | None,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve one filtered page and translate UUIDs for the agent."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [memory_type],
        skip,
        limit,
        marks=[mark],
        term_search=term_search,
    )
    return to_agent_memory_page(ctx, page)


def strip_marker(content: str, category: str) -> str:
    """Remove legacy category prefixes from agent-supplied memory prose."""
    marker = f"[{category}]"
    while content.startswith(marker):
        content = content.removeprefix(marker).lstrip()
    return content


def create_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: list[str],
    mem_type: MemoryType,
    scope: Scope | None,
    tool_name: str,
    mark: str | None = None,
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
                mark,
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
                f"Missing glossary terms: {serialized_terms}. If add_term is available, call it once for each "
                f"eligible missing exact term, wait for those calls to succeed, then retry {tool_name} with "
                "the same content, scope, and complete term_names list. If add_term is not available, do not "
                "retry this write."
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
    mark: str | None = None,
    replacement_term_names: list[str] | None = None,
    *,
    expected_marks: list[str | None] | None = None,
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
                mark,
                replacement_term_names,
                expected_marks,
            )
    except GlossaryTermNotFoundException as exc:
        missing_term_names = access.get_missing_term_names(
            ctx.deps.db,
            ctx.deps.mem_access_context.memory_group_id,
            replacement_term_names or [],
        )
        serialized_terms = json.dumps(missing_term_names, ensure_ascii=False)
        raise ModelRetry(
            f"Missing replacement glossary terms: {serialized_terms}. If add_term is available, add each "
            "eligible missing exact term, then retrieve the original memory again and retry supersession. "
            "If add_term is not available, do not retry this write."
        ) from exc
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
    *,
    marks: list[str | None] | None = None,
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
                marks=marks,
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

    def translate(glossary_memory: AgentGlossaryMemory[UUID]) -> AgentGlossaryMemory[str]:
        return AgentGlossaryMemory[str](
            memory=AgentMemory[str].model_validate(
                {
                    **glossary_memory.memory.model_dump(),
                    "memory_id": ctx.deps.uuid_cache.new(glossary_memory.memory.memory_id),
                }
            ),
            terms=glossary_memory.terms,
        )

    rows = [translate(glossary_memory) for glossary_memory in page.rows]
    if isinstance(page, AgentGlossaryMemoryPage):
        return AgentGlossaryMemoryPage[str](
            count=page.count,
            rows=rows,
            aliases=[translate(glossary_memory) for glossary_memory in page.aliases],
            aliases_truncated=page.aliases_truncated,
        )
    return Page[AgentGlossaryMemory[str]](count=page.count, rows=rows)


def to_agent_alias_memory_page(
    ctx: RunContext[MemAgentDeps], page: AgentGlossaryMemoryPage[UUID]
) -> AgentGlossaryMemoryPage[str]:
    """Translate the alias-aware page shape exposed by shared readers."""
    converted = to_agent_memory_page(ctx, page)
    if not isinstance(converted, AgentGlossaryMemoryPage):
        raise RuntimeError("Alias-aware glossary retrieval lost its alias context")
    return converted
