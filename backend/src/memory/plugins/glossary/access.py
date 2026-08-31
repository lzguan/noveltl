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
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryTerm
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
) -> Page[AgentGlossaryMemory[UUID]]:
    # TODO: Make retrieval alias-aware. Exact-name lookup can miss a conflicting
    # memory stored under another alias of the same entity. This likely needs a
    # structured alias relation or shared entity identity; expanding every free-
    # text relation would incorrectly merge other kinds of related terms.
    chap_num, _ = check_mem_access_ctx(db, ctx)
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
            build_memory_query()
            .order_by(Memory.memory_start_num.desc(), Memory.memory_id)
            .offset(skip)
            .limit(limit)
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
    return Page[AgentGlossaryMemory[UUID]](
        count=count,
        rows=[
            AgentGlossaryMemory[UUID](
                memory=AgentMemory.model_validate(memory),
                terms=terms_by_memory[memory.memory_id],
            )
            for memory in memories
        ],
    )


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
) -> tuple[Memory, list[GlossaryAssociation]]:
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
) -> None:
    """End an older active glossary memory without creating a replacement."""
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    try:
        db.execute(
            update(Memory)
            .where(
                Memory.memory_id == memory_id,
                Memory.memory_group_id == ctx.memory_group_id,
                Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
                Memory.memory_type.in_(memory_types),
                Memory.memory_start_num < chapter_num,
                or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter_num),
            )
            .values(memory_end_num=chapter_num)
            .returning(Memory.memory_id)
        ).scalar_one()
    except NoResultFound as exc:
        raise MemoryNotFoundException(f"Glossary memory with id {memory_id} not found or already ended") from exc
