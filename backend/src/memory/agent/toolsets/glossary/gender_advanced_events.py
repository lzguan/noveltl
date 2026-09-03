from typing import Annotated, Literal, get_args

from pydantic import Field
from pydantic_ai import FunctionToolset, RunContext

from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import MemoryType, Scope
from src.schemas import Page

type GenderEventKind = Literal[
    "transformation",
    "body_swap",
    "possession",
    "reveal",
]
GENDER_EVENT_KINDS: tuple[GenderEventKind, ...] = get_args(GenderEventKind.__value__)
GENDER_EVENT_MARKS: dict[GenderEventKind, str] = {kind: f"gender.event.{kind}" for kind in GENDER_EVENT_KINDS}

GLOSSARY_ADVANCED_GENDER_EVENT_READ_INSTRUCTIONS = """
Use `gender_event_memories` to retrieve one kind of gender-related event for
one exact recurring person. Results are newest-first. Use active-only results
for current continuity and include ended history only when the chapter
explicitly refers to an earlier occurrence.
""".strip()

GLOSSARY_ADVANCED_GENDER_EVENT_WRITE_INSTRUCTIONS = """
EVENT DEFINITION: A gender event is a bounded, consequential occurrence that
changes, exchanges, restores, or reveals gender-related context. It
answers "What happened?" or "How was the context changed or revealed?" and is
useful later as history even after the resulting current state is already
known. Record only a transformation, body swap, possession, or reveal. Store
one short atomic occurrence and associate only recurring principal terms.

Semantic event examples:
- `transformation`: `During the eclipse ritual, 林玥's body permanently changed
  from male to female.`
- `body_swap`: `林玥 and 沈秋 exchanged bodies when the mirror shattered.`
- `possession`: `林玥 entered and took control of 沈秋's body.`
- `reveal`: `林玥 revealed that the identity known as 林公子 had always been a
  disguise.`

Not events: `林玥's current body is female` and `林玥 self-identifies as male`
are current-state facts; wearing different clothing for one scene is not a
durable event; attraction, embarrassment, adaptation, menstruation, pronoun
use, and another character's mistaken assumption are not gender events. The
start or end of a disguise, cover identity, or assumed persona belongs to a
disguise toolset when one is provided and must otherwise be ignored.

Choose the most specific event kind. `transformation` means the subject's body
changes without exchanging occupants; `body_swap` means occupants exchange
bodies; `possession` means an occupant enters or controls another body;
`reveal` discloses an existing truth without changing it and does not include
beginning or ending a disguise.

Do not record every routine activation of a repeatable transformation. Store
the durable trigger or mechanic as a `change_rule` fact. Record a particular
activation as an event only when its occurrence or immediate consequence is
independently important to later continuity.

Enabled advanced gender fact tools separately maintain what is currently true.
A reveal may create or correct a fact but does not represent an in-world state
change. A temporary transformation may be an event without replacing canonical
body state. A persistent transformation may warrant both an event and a
body-state supersession. Record both only when each is independently useful:
the event preserves the occurrence and transition, while the fact preserves
only the resulting current state. Never copy the same sentence into both.

Before writing an occurrence that may duplicate, correct, or replace an older
one, retrieve the same person and event kind. Supersede only a correction or
replacement of that exact occurrence. A later distinct occurrence is a new
event. Default to `recent`; reserve `persist` for irreversible or
identity-shaping occurrences.
""".strip()


def gender_event_memories(
    ctx: RunContext[MemAgentDeps],
    term_name: Annotated[str, Field(min_length=1)],
    event_kind: GenderEventKind,
    skip: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
    active_only: bool = True,
) -> Page[AgentGlossaryMemory[str]]:
    """Retrieve one kind of gender-related event for one exact person term."""
    page = access.inspect_terms(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        [term_name],
        [MemoryType.EVENT],
        skip,
        limit,
        active_only=active_only,
        marks=[GENDER_EVENT_MARKS[event_kind]],
    )
    return common.to_agent_memory_page(ctx, page)


def new_gender_event_memory(
    ctx: RunContext[MemAgentDeps],
    content: str,
    term_names: Annotated[list[str], Field(min_length=1)],
    event_kind: GenderEventKind,
    scope: Scope | None = None,
) -> str:
    """Create one categorized consequential gender-related event."""
    mark = GENDER_EVENT_MARKS[event_kind]
    return common.create_memory(
        ctx,
        common.strip_marker(content, mark),
        term_names,
        MemoryType.EVENT,
        scope,
        "new_gender_event_memory",
        mark,
    )


def supersede_gender_event_memory(
    ctx: RunContext[MemAgentDeps],
    memory_id: str,
    content: str,
    event_kind: GenderEventKind,
    scope: Scope | None = None,
) -> str:
    """Correct or replace one earlier gender-related occurrence."""
    mark = GENDER_EVENT_MARKS[event_kind]
    return common.supersede_memory(
        ctx,
        memory_id,
        common.strip_marker(content, mark),
        MemoryType.EVENT,
        scope,
        mark,
        expected_marks=[mark],
    )


glossary_gender_advanced_events_read_toolset = FunctionToolset(
    tools=[gender_event_memories],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_ADVANCED_GENDER_EVENT_READ_INSTRUCTIONS],
    sequential=True,
)

glossary_gender_advanced_events_write_toolset = FunctionToolset(
    tools=[new_gender_event_memory, supersede_gender_event_memory],
    instructions=[GLOSSARY_ADVANCED_GENDER_EVENT_WRITE_INSTRUCTIONS],
    sequential=True,
)
