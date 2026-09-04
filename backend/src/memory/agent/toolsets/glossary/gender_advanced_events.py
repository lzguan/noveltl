import json
from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import Field
from pydantic_ai import FunctionToolset, ModelRetry, RunContext
from sqlalchemy import or_, select

from src.memory.access import check_mem_access_ctx
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary import common
from src.memory.agent.types import OccurrenceRetentionConfig
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.models import Memory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.schemas import Page

type GenderEventKind = Literal[
    "transformation",
    "body_swap",
    "possession",
    "reveal",
]
type OtherGenderEventKind = Literal["body_swap", "possession", "reveal"]
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
For a transformation, associate only the exact transformed subject through
`new_gender_transformation_event_memory`; the application manages its active
history. Correct it through `supersede_gender_transformation_event_memory` with
the same exact subject. Use the generic create and supersede event tools for
the other event kinds.

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
event. For non-transformation events, default to `recent` and reserve `persist`
for irreversible or identity-shaping occurrences. Transformation scope and
retention are controlled by the application; do not manually expire events to
enforce that policy.
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
    event_kind: OtherGenderEventKind,
    scope: Scope | None = None,
) -> str:
    """Create one body-swap, possession, or reveal event."""
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


glossary_gender_advanced_events_read_toolset = FunctionToolset(
    tools=[gender_event_memories],
    instructions=[common.GLOSSARY_READ_SUPPORT_INSTRUCTIONS, GLOSSARY_ADVANCED_GENDER_EVENT_READ_INSTRUCTIONS],
    sequential=True,
)


def create_glossary_gender_advanced_events_write_toolset(
    config: OccurrenceRetentionConfig,
) -> FunctionToolset[MemAgentDeps]:
    """Build advanced gender-event writers with one job's retention policy."""
    retention = config

    def new_gender_transformation_event_memory(
        ctx: RunContext[MemAgentDeps],
        subject_term_name: Annotated[str, Field(min_length=1)],
        content: str,
    ) -> str:
        """Create a transformation for one exact subject under configured retention."""
        mark = GENDER_EVENT_MARKS["transformation"]
        db = ctx.deps.db
        try:
            with db.begin_nested():
                new_memory, _ = access.create_memory(
                    db,
                    ctx.deps.mem_access_context,
                    Creator.AGENT,
                    MemoryType.EVENT,
                    [subject_term_name],
                    common.strip_marker(content, mark),
                    Scope.PERSIST,
                    mark,
                )
                chapter_num, _ = check_mem_access_ctx(db, ctx.deps.mem_access_context)
                memories = list(
                    db.scalars(
                        select(Memory)
                        .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
                        .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
                        .where(
                            GlossaryTerm.memory_group_id == ctx.deps.mem_access_context.memory_group_id,
                            GlossaryTerm.term == subject_term_name,
                            Memory.memory_group_id == ctx.deps.mem_access_context.memory_group_id,
                            Memory.plugin_name == access.GLOSSARY_PLUGIN_NAME,
                            Memory.memory_type == MemoryType.EVENT,
                            Memory.mark == mark,
                            Memory.creator_type == Creator.AGENT,
                            Memory.memory_review_status != ReviewStatus.REJECTED,
                            Memory.memory_start_num <= chapter_num,
                        )
                        .order_by(Memory.memory_start_num, Memory.memory_id)
                    ).all()
                )
                memories_by_id = {memory.memory_id: memory for memory in memories}
                # A correction starts a newer database row, but it is not a new
                # occurrence. Follow supersession links so it keeps the original
                # occurrence's chapter and position in the retention window.
                # If another tool needs this retention behavior, move it to the
                # appropriate shared layer in glossary common or access code.
                roots_by_memory: dict[UUID, UUID] = {}
                for memory in memories:
                    current = memory
                    visited: set[UUID] = set()
                    while current.supersedes_memory_id in memories_by_id and current.memory_id not in visited:
                        visited.add(current.memory_id)
                        current = memories_by_id[current.supersedes_memory_id]
                    roots_by_memory[memory.memory_id] = current.memory_id

                active_memories = [
                    memory
                    for memory in memories
                    if memory.memory_end_num is None or memory.memory_end_num > chapter_num
                ]
                occurrence_roots = sorted(
                    {roots_by_memory[memory.memory_id] for memory in active_memories},
                    key=lambda memory_id: (
                        memories_by_id[memory_id].memory_start_num,
                        memory_id.int,
                    ),
                )
                stop = (
                    len(occurrence_roots) - retention.keep_rolling
                    if retention.keep_rolling
                    else len(occurrence_roots)
                )
                expired_roots = set(occurrence_roots[retention.keep_first : max(retention.keep_first, stop)])
                for memory in active_memories:
                    if roots_by_memory[memory.memory_id] in expired_roots:
                        access.expire_memory(
                            db,
                            ctx.deps.mem_access_context,
                            memory.memory_id,
                            [MemoryType.EVENT],
                            marks=[mark],
                            end_offset=1 if memory.memory_start_num == chapter_num else 0,
                        )
        except GlossaryTermNotFoundException as exc:
            missing_term_names = access.get_missing_term_names(
                db,
                ctx.deps.mem_access_context.memory_group_id,
                [subject_term_name],
            )
            if missing_term_names:
                serialized_terms = json.dumps(missing_term_names, ensure_ascii=False)
                raise ModelRetry(
                    f"Missing glossary terms: {serialized_terms}. If add_term is available, call it for the "
                    "eligible missing exact term, wait for that call to succeed, then retry "
                    "new_gender_transformation_event_memory with the same content and subject_term_name. "
                    "If add_term is not available, do not retry this write."
                ) from exc
            raise ModelRetry(
                "Every memory must reference a glossary term. Supply the intended exact source term as "
                "subject_term_name, then retry new_gender_transformation_event_memory."
            ) from exc
        return ctx.deps.uuid_cache.new(new_memory.memory_id)

    def supersede_gender_transformation_event_memory(
        ctx: RunContext[MemAgentDeps],
        memory_id: str,
        subject_term_name: Annotated[str, Field(min_length=1)],
        content: str,
    ) -> str:
        """Correct one transformation occurrence for its exact subject."""
        mark = GENDER_EVENT_MARKS["transformation"]
        try:
            current_id = ctx.deps.uuid_cache.get_uuid(memory_id)
        except KeyError as exc:
            raise ModelRetry(f"Memory {memory_id} not found.") from exc

        chapter_num, _ = check_mem_access_ctx(ctx.deps.db, ctx.deps.mem_access_context)
        target_exists = ctx.deps.db.scalar(
            select(Memory.memory_id)
            .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
            .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
            .where(
                Memory.memory_id == current_id,
                Memory.memory_group_id == ctx.deps.mem_access_context.memory_group_id,
                Memory.plugin_name == access.GLOSSARY_PLUGIN_NAME,
                Memory.memory_type == MemoryType.EVENT,
                Memory.mark == mark,
                Memory.creator_type == Creator.AGENT,
                Memory.memory_review_status != ReviewStatus.REJECTED,
                Memory.memory_start_num < chapter_num,
                or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter_num),
                GlossaryTerm.memory_group_id == ctx.deps.mem_access_context.memory_group_id,
                GlossaryTerm.term == subject_term_name,
            )
        )
        if target_exists is None:
            raise ModelRetry(
                f"Memory {memory_id} does not exist, has already ended, belongs to another subject or event "
                "kind, or cannot be superseded in this chapter. Do not retry this memory handle; retrieve "
                "the exact subject's current transformation history before making a different call."
            )

        return common.supersede_memory(
            ctx,
            memory_id,
            common.strip_marker(content, mark),
            MemoryType.EVENT,
            Scope.PERSIST,
            mark,
            replacement_term_names=[subject_term_name],
            expected_marks=[mark],
        )

    def supersede_gender_event_memory(
        ctx: RunContext[MemAgentDeps],
        memory_id: str,
        content: str,
        event_kind: OtherGenderEventKind,
        scope: Scope | None = None,
    ) -> str:
        """Correct or replace one body-swap, possession, or reveal occurrence."""
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

    retention_instructions = (
        "Transformation retention is automatic for each exact subject: keep the first "
        f"{retention.keep_first} occurrence(s) and a FIFO window of the newest "
        f"{retention.keep_rolling} occurrence(s). Overlap is counted once. Do not change scope or "
        "expire transformation events to implement this policy."
    )
    return FunctionToolset(
        tools=[
            new_gender_transformation_event_memory,
            supersede_gender_transformation_event_memory,
            new_gender_event_memory,
            supersede_gender_event_memory,
        ],
        instructions=[GLOSSARY_ADVANCED_GENDER_EVENT_WRITE_INSTRUCTIONS, retention_instructions],
        sequential=True,
    )


glossary_gender_advanced_events_write_toolset = create_glossary_gender_advanced_events_write_toolset(
    OccurrenceRetentionConfig()
)
