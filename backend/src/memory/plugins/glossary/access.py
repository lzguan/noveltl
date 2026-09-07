from collections.abc import Callable, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import SQLColumnExpression, func, insert, literal, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from src.memory.access import MemAccessContext, check_mem_access_ctx, write_memory
from src.memory.exceptions import GlossaryTermNotFoundException, MemoryNotFoundException
from src.memory.models import Memory
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryMemoryPage, AgentGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentMemory
from src.memory.types import Creator, MemoryType, PluginName, ReviewStatus, Scope
from src.novels.models import ChapterContent
from src.schemas import Page

type ContainsQuery = Callable[
    [SQLColumnExpression[str], SQLColumnExpression[str]],
    SQLColumnExpression[bool],
]

GLOSSARY_PLUGIN_NAME: Final[PluginName] = "glossary"
ALIAS_MARK: Final = "alias"
MAX_ALIAS_TERMS: Final = 32
MAX_ALIAS_EDGES: Final = 64


def contains_query(chapter: SQLColumnExpression[str], term: SQLColumnExpression[str]) -> SQLColumnExpression[bool]:
    """Match terms after removing known source-text obfuscation marks."""
    normalized_chapter = func.translate(chapter, "『』《》【】", "")
    normalized_term = func.translate(term, "『』《》【】", "")
    return normalized_chapter.contains(normalized_term)


def get_terms_in_chapter(
    db: Session,
    ctx: MemAccessContext,
    contains_query: ContainsQuery,
    *,
    include_rejected: bool = False,
) -> list[GlossaryTerm]:
    """Get glossary terms occurring in the exact chapter content pinned by the context."""
    check_mem_access_ctx(db, ctx)
    query = (
        select(GlossaryTerm)
        .select_from(ChapterContent)
        .join(
            GlossaryTerm,
            contains_query(ChapterContent.chapter_content_text, GlossaryTerm.term),
        )
        .where(
            ChapterContent.chapter_content_id == ctx.chapter_content_id,
            ChapterContent.chapter_id == ctx.chapter_id,
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
        )
        .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
    )
    if not include_rejected:
        query = query.where(GlossaryTerm.review_status != ReviewStatus.REJECTED)
    return list(db.scalars(query).all())


def inspect_terms(
    db: Session,
    ctx: MemAccessContext,
    term_names: list[str],
    memory_types: Sequence[MemoryType] | None,
    skip: int = 0,
    limit: int = 100,
    *,
    active_only: bool = True,
    include_rejected: bool = False,
    marks: Sequence[str | None] | None = None,
    term_search: str | None = None,
    expand_aliases: bool = False,
) -> Page[AgentGlossaryMemory[UUID]]:
    chap_num, _ = check_mem_access_ctx(db, ctx)
    alias_memories: list[Memory] = []
    aliases_truncated = False
    if expand_aliases:
        term_names, alias_memories, aliases_truncated = _expand_alias_terms(db, ctx, chap_num, term_names)

    matching_association = aliased(GlossaryAssociation)
    matching_term = aliased(GlossaryTerm)
    matching_memory_ids = (
        select(matching_association.memory_id)
        .join(matching_term, matching_term.term_id == matching_association.term_id)
        .where(
            matching_term.term.in_(term_names),
            matching_term.memory_group_id == ctx.memory_group_id,
        )
        .distinct()
    )
    if not include_rejected:
        matching_memory_ids = matching_memory_ids.where(matching_term.review_status != ReviewStatus.REJECTED)

    def build_memory_query():
        query = select(Memory).where(
            Memory.memory_id.in_(matching_memory_ids),
            Memory.memory_group_id == ctx.memory_group_id,
            Memory.memory_start_num <= chap_num,
            Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
        )
        if active_only:
            query = query.where(or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chap_num))
        if not include_rejected:
            query = query.where(Memory.memory_review_status != ReviewStatus.REJECTED)
        if memory_types is not None:
            query = query.where(Memory.memory_type.in_(memory_types))
        if marks is not None:
            non_null_marks = [mark for mark in marks if mark is not None]
            mark_filters = []
            if non_null_marks:
                mark_filters.append(Memory.mark.in_(non_null_marks))
            if None in marks:
                mark_filters.append(Memory.mark.is_(None))
            query = query.where(or_(*mark_filters) if mark_filters else Memory.mark.in_([]))
        if term_search is not None:
            query = query.where(Memory.memory_content.icontains(term_search, autoescape=True))
        return query

    count = db.scalar(select(func.count()).select_from(build_memory_query().subquery())) or 0
    memories = list(
        db.scalars(
            build_memory_query().order_by(Memory.memory_start_num.desc(), Memory.memory_id).offset(skip).limit(limit)
        ).all()
    )
    memory_ids = [memory.memory_id for memory in memories]
    terms_query = (
        select(GlossaryAssociation.memory_id, GlossaryTerm)
        .select_from(GlossaryAssociation)
        .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
        .where(
            GlossaryAssociation.memory_id.in_(memory_ids),
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
        )
        .order_by(GlossaryAssociation.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
    )
    if not include_rejected:
        terms_query = terms_query.where(GlossaryTerm.review_status != ReviewStatus.REJECTED)

    terms_by_memory: dict[UUID, list[AgentGlossaryTerm]] = {memory_id: [] for memory_id in memory_ids}
    for memory_id, term in db.execute(terms_query).tuples():
        terms_by_memory[memory_id].append(AgentGlossaryTerm.model_validate(term))
    rows = [
        AgentGlossaryMemory[UUID](
            memory=AgentMemory.model_validate(memory),
            terms=terms_by_memory[memory.memory_id],
        )
        for memory in memories
    ]
    if expand_aliases:
        return AgentGlossaryMemoryPage[UUID](
            count=count,
            rows=rows,
            aliases=_agent_glossary_memories(db, ctx.memory_group_id, alias_memories, include_rejected),
            aliases_truncated=aliases_truncated,
        )
    return Page[AgentGlossaryMemory[UUID]](count=count, rows=rows)


def _agent_glossary_memories(
    db: Session,
    memory_group_id: UUID,
    memories: Sequence[Memory],
    include_rejected: bool,
) -> list[AgentGlossaryMemory[UUID]]:
    """Attach original term forms to an already ordered collection of memories."""
    memory_ids = [memory.memory_id for memory in memories]
    if not memory_ids:
        return []
    query = (
        select(GlossaryAssociation.memory_id, GlossaryTerm)
        .select_from(GlossaryAssociation)
        .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
        .where(GlossaryAssociation.memory_id.in_(memory_ids), GlossaryTerm.memory_group_id == memory_group_id)
        .order_by(GlossaryAssociation.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
    )
    if not include_rejected:
        query = query.where(GlossaryTerm.review_status != ReviewStatus.REJECTED)
    terms_by_memory: dict[UUID, list[AgentGlossaryTerm]] = {memory_id: [] for memory_id in memory_ids}
    for memory_id, term in db.execute(query).tuples():
        terms_by_memory[memory_id].append(AgentGlossaryTerm.model_validate(term))
    return [
        AgentGlossaryMemory[UUID](memory=AgentMemory.model_validate(memory), terms=terms_by_memory[memory.memory_id])
        for memory in memories
    ]


def _expand_alias_terms(
    db: Session,
    ctx: MemAccessContext,
    chapter_num: int,
    term_names: Sequence[str],
) -> tuple[list[str], list[Memory], bool]:
    """Expand active pair aliases with bounded deterministic traversal.

    Legacy aliases with more than two terms are deliberately ignored: they may
    describe a broad relation rather than pairwise identity equivalence.
    """
    initial_terms = list(
        db.scalars(
            select(GlossaryTerm.term)
            .where(
                GlossaryTerm.memory_group_id == ctx.memory_group_id,
                GlossaryTerm.term.in_(term_names),
                GlossaryTerm.review_status != ReviewStatus.REJECTED,
            )
            .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
        ).all()
    )
    if not initial_terms:
        return list(term_names), [], False

    alias_rows = list(
        db.execute(
            select(Memory, GlossaryTerm)
            .select_from(Memory)
            .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
            .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
            .where(
                Memory.memory_group_id == ctx.memory_group_id,
                Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
                Memory.memory_type == MemoryType.RELATION,
                Memory.mark == ALIAS_MARK,
                Memory.memory_review_status != ReviewStatus.REJECTED,
                Memory.memory_start_num <= chapter_num,
                or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter_num),
                GlossaryTerm.memory_group_id == ctx.memory_group_id,
            )
            .order_by(Memory.memory_start_num.desc(), Memory.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
        ).tuples()
    )
    terms_by_alias: dict[UUID, list[GlossaryTerm]] = {}
    memories_by_id: dict[UUID, Memory] = {}
    for memory, term in alias_rows:
        memories_by_id[memory.memory_id] = memory
        terms_by_alias.setdefault(memory.memory_id, []).append(term)

    adjacency: dict[str, list[tuple[str, Memory]]] = {}
    for memory_id, terms in terms_by_alias.items():
        if len(terms) != 2 or any(term.review_status == ReviewStatus.REJECTED for term in terms):
            continue
        first, second = terms
        memory = memories_by_id[memory_id]
        adjacency.setdefault(first.term, []).append((second.term, memory))
        adjacency.setdefault(second.term, []).append((first.term, memory))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], -item[1].memory_start_num, str(item[1].memory_id)))

    reached = set(initial_terms)
    queue = list(initial_terms)
    used_edges: list[Memory] = []
    used_edge_ids: set[UUID] = set()
    truncated = False
    while queue:
        current = queue.pop(0)
        for other, memory in adjacency.get(current, []):
            if memory.memory_id in used_edge_ids:
                continue
            if len(used_edges) >= MAX_ALIAS_EDGES:
                truncated = True
                break
            if other not in reached and len(reached) >= MAX_ALIAS_TERMS:
                truncated = True
                continue
            used_edge_ids.add(memory.memory_id)
            used_edges.append(memory)
            if other not in reached:
                reached.add(other)
                queue.append(other)
        if truncated and len(used_edges) >= MAX_ALIAS_EDGES:
            break
    return sorted(reached), used_edges, truncated


def create_term(
    db: Session,
    memory_group_id: UUID,
    term_name: str,
    term_kind: TermKind | None = None,
) -> GlossaryTerm:
    return db.execute(
        insert(GlossaryTerm)
        .values(memory_group_id=memory_group_id, term=term_name, term_kind=term_kind)
        .returning(GlossaryTerm)
    ).scalar_one()


def _set_term_review_status(
    db: Session,
    memory_group_id: UUID,
    term_id: UUID,
    review_status: ReviewStatus,
) -> GlossaryTerm:
    try:
        return db.execute(
            update(GlossaryTerm)
            .where(GlossaryTerm.term_id == term_id, GlossaryTerm.memory_group_id == memory_group_id)
            .values(review_status=review_status)
            .returning(GlossaryTerm)
        ).scalar_one()
    except NoResultFound as e:
        raise GlossaryTermNotFoundException(f"Glossary term with id {term_id} not found") from e


def approve_term(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.APPROVED)


def reject_term(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.REJECTED)


def mark_term_pending(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.PENDING)


def get_missing_term_names(db: Session, memory_group_id: UUID, term_names: list[str]) -> list[str]:
    """Return requested glossary terms that do not exist in the memory group."""
    unique_term_names = list(dict.fromkeys(term_names))
    existing_term_names = set(
        db.scalars(
            select(GlossaryTerm.term).where(
                GlossaryTerm.memory_group_id == memory_group_id,
                GlossaryTerm.term.in_(unique_term_names),
            )
        ).all()
    )
    return [term_name for term_name in unique_term_names if term_name not in existing_term_names]


def _associate_terms(
    db: Session,
    memory_group_id: UUID,
    memory_id: UUID,
    term_names: list[str],
) -> list[GlossaryAssociation]:
    unique_term_names = list(dict.fromkeys(term_names))
    if not unique_term_names:
        return []
    association_source = select(
        GlossaryTerm.term_id,
        literal(memory_id),
    ).where(
        GlossaryTerm.term.in_(unique_term_names),
        GlossaryTerm.memory_group_id == memory_group_id,
    )
    associations = (
        db.execute(
            insert(GlossaryAssociation)
            .from_select(
                [GlossaryAssociation.term_id, GlossaryAssociation.memory_id],
                association_source,
            )
            .returning(GlossaryAssociation)
        )
        .scalars()
        .all()
    )
    if len(associations) != len(unique_term_names):
        raise GlossaryTermNotFoundException("Some terms do not exist in the memory group.")
    return list(associations)


def create_memory(
    db: Session,
    ctx: MemAccessContext,
    creator: Creator,
    mem_type: MemoryType,
    term_names: list[str],
    content: str,
    scope: Scope | None = None,
    mark: str | None = None,
) -> tuple[Memory, list[GlossaryAssociation]]:
    new_memory = write_memory(
        db,
        ctx,
        mem_type,
        content,
        creator,
        GLOSSARY_PLUGIN_NAME,
        scope,
        mark=mark,
    )
    glossary_associations = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, term_names)
    return new_memory, list(glossary_associations)


def supersede_memory(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    creator: Creator,
    mem_type: MemoryType,
    content: str,
    scope: Scope | None = None,
    mark: str | None = None,
    replacement_term_names: list[str] | None = None,
    expected_marks: Sequence[str | None] | None = None,
) -> tuple[Memory, list[GlossaryAssociation]]:
    target_query = select(Memory.memory_id).where(
        Memory.memory_id == memory_id,
        Memory.memory_group_id == ctx.memory_group_id,
        Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
        Memory.memory_type == mem_type,
    )
    if expected_marks is not None:
        non_null_marks = [expected_mark for expected_mark in expected_marks if expected_mark is not None]
        mark_filters = []
        if non_null_marks:
            mark_filters.append(Memory.mark.in_(non_null_marks))
        if None in expected_marks:
            mark_filters.append(Memory.mark.is_(None))
        target_query = target_query.where(or_(*mark_filters) if mark_filters else Memory.mark.in_([]))
    if db.scalar(target_query) is None:
        raise MemoryNotFoundException(f"Glossary memory with id {memory_id} is outside this toolset")

    if replacement_term_names is None:
        replacement_term_names = list(
            db.execute(
                select(GlossaryTerm.term)
                .select_from(GlossaryAssociation)
                .where(GlossaryAssociation.memory_id == memory_id)
                .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
                .where(
                    GlossaryTerm.memory_group_id == ctx.memory_group_id,
                )
            )
            .scalars()
            .all()
        )
    new_memory = write_memory(
        db,
        ctx,
        mem_type,
        content,
        creator,
        GLOSSARY_PLUGIN_NAME,
        scope,
        supersedes_id=memory_id,
        mark=mark,
    )
    new_assocs = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, replacement_term_names)
    return new_memory, new_assocs


def expire_memory(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    memory_types: Sequence[MemoryType],
    *,
    marks: Sequence[str | None] | None = None,
    end_offset: int = 0,
) -> None:
    """End an active glossary memory at the context chapter plus an internal offset."""
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    end_num = chapter_num + end_offset
    try:
        query = update(Memory).where(
            Memory.memory_id == memory_id,
            Memory.memory_group_id == ctx.memory_group_id,
            Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
            Memory.memory_type.in_(memory_types),
            Memory.memory_start_num < end_num,
            or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter_num),
        )
        if marks is not None:
            non_null_marks = [mark for mark in marks if mark is not None]
            mark_filters = []
            if non_null_marks:
                mark_filters.append(Memory.mark.in_(non_null_marks))
            if None in marks:
                mark_filters.append(Memory.mark.is_(None))
            query = query.where(or_(*mark_filters) if mark_filters else Memory.mark.in_([]))
        db.execute(query.values(memory_end_num=end_num).returning(Memory.memory_id)).scalar_one()
    except NoResultFound as exc:
        raise MemoryNotFoundException(f"Glossary memory with id {memory_id} not found or already ended") from exc
