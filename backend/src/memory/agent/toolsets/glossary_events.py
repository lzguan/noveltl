from typing import Annotated

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

GLOSSARY_EVENT_INSTRUCTIONS = """
Maintain consequential events associated with exact source-language glossary
terms.

- `term_event_memories`: inspect events associated with specific exact terms.
  Results are newest-first and may include events associated with only some
  requested terms. Use `active_only=True` for current continuity. Set it to
  false only when older, expired, or superseded history is relevant. Start with
  the default page and request another page only when needed.
- `new_term_event_memory`: record a short, atomic consequential occurrence or
  change. Every associated term must already exist. For an eligible missing
  term, call `add_term` when that tool is available; otherwise omit the event.
- `supersede_term_event_memory`: supersede an active event from an earlier
  chapter only when the current chapter corrects, replaces, or ends it. Do not
  use it on an event created in the current chapter or merely to append a
  compatible later occurrence.

An event includes a death, meeting, discovery, promise, relocation,
acquisition, loss, conflict outcome, or irreversible transformation. Record
only the consequential action and outcome, not a chapter summary. Associate
only the principal participants or entities needed to retrieve it.

Default to `recent`; use `persist` only for an irreversible or identity-shaping
event. If only the resulting state or relationship matters, use an enabled fact
or relation toolset instead of duplicating it as an event. A clearly new
standalone event may skip retrieval; retrieve event history when a candidate
continues, concludes, or may duplicate an earlier occurrence.

For the shared lifecycle decision, the tracked claim is one occurrence or one
continuous development. A correction, completion, or replacement of that same
occurrence may supersede it. A later compatible occurrence is a separate event,
and a clearly standalone new event does not require speculative retrieval.
""".strip()


def term_event_memories(
    ctx: RunContext[MemAgentDeps],
    term_names: Annotated[list[str], Field(min_length=1)],
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
    active_only: bool = True,
) -> Page[AgentGlossaryMemory[str]]:
    """See a page of events associated with exact glossary terms."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        term_names,
        [MemoryType.EVENT],
        skip,
        limit,
        active_only=active_only,
    )
    return glossary_common.to_agent_memory_page(ctx, page)


def new_term_event_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1)],
    scope: Scope | None = None,
) -> str:
    """Create an event associated with existing exact glossary terms."""
    return glossary_common.create_memory(
        ctx,
        content,
        term_names,
        MemoryType.EVENT,
        scope,
        "new_term_event_memory",
    )


def supersede_term_event_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    scope: Scope | None = None,
) -> str:
    """Supersede an active event from an earlier chapter."""
    return glossary_common.supersede_memory(ctx, memory_id, content, MemoryType.EVENT, scope)


glossary_event_toolset = FunctionToolset(
    tools=[term_event_memories, new_term_event_memory, supersede_term_event_memory],
    instructions=[GLOSSARY_EVENT_INSTRUCTIONS],
    sequential=True,
)
