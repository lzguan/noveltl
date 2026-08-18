from collections.abc import Callable
from uuid import UUID

from sqlalchemy import SQLColumnExpression, insert, literal, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from src.memory.access import MemAccessContext, check_mem_access_ctx, write_memory
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.models import Memory
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.novels.models import ChapterContent

type ContainsQuery = Callable[
    [SQLColumnExpression[str], SQLColumnExpression[str]],
    SQLColumnExpression[bool],
]


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
    term_ids: list[UUID],
    *,
    include_rejected: bool = False,
) -> list[tuple[Memory, list[GlossaryTerm]]]:
    chap_num, _ = check_mem_access_ctx(db, ctx)
    matching_association = aliased(GlossaryAssociation)
    matching_term = aliased(GlossaryTerm)
    matching_memory_ids = (
        select(matching_association.memory_id)
        .join(matching_term, matching_term.term_id == matching_association.term_id)
        .where(
            matching_term.term_id.in_(term_ids),
            matching_term.memory_group_id == ctx.memory_group_id,
        )
        .distinct()
    )
    if not include_rejected:
        matching_memory_ids = matching_memory_ids.where(matching_term.review_status != ReviewStatus.REJECTED)
    query = (
        select(Memory, GlossaryTerm)
        .select_from(Memory)
        .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
        .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
        .where(
            Memory.memory_id.in_(matching_memory_ids),
            Memory.memory_group_id == ctx.memory_group_id,
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
            Memory.memory_start_num <= chap_num,
            or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chap_num),
        )
        .order_by(Memory.memory_start_num.desc(), Memory.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
    )
    if not include_rejected:
        query = query.where(
            Memory.memory_review_status != ReviewStatus.REJECTED, GlossaryTerm.review_status != ReviewStatus.REJECTED
        )

    memories_with_terms: dict[UUID, tuple[Memory, list[GlossaryTerm]]] = {}
    for memory, term in db.execute(query).tuples():
        if memory.memory_id not in memories_with_terms:
            memories_with_terms[memory.memory_id] = (memory, [])
        memories_with_terms[memory.memory_id][1].append(term)
    return list(memories_with_terms.values())


def create_term(db: Session, memory_group_id: UUID, term_name: str) -> GlossaryTerm:
    return db.execute(
        insert(GlossaryTerm).values(memory_group_id=memory_group_id, term=term_name).returning(GlossaryTerm)
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


def _associate_terms(
    db: Session,
    memory_group_id: UUID,
    memory_id: UUID,
    term_ids: list[UUID],
) -> list[GlossaryAssociation]:
    unique_term_ids = list(dict.fromkeys(term_ids))
    if not unique_term_ids:
        raise ValueError("A glossary memory must be associated with at least one term.")

    association_source = select(
        GlossaryTerm.term_id,
        literal(memory_id),
    ).where(
        GlossaryTerm.term_id.in_(unique_term_ids),
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
    if len(associations) != len(unique_term_ids):
        raise ValueError("Some terms do not exist in the memory group.")
    return list(associations)


def create_memory(
    db: Session,
    ctx: MemAccessContext,
    creator: Creator,
    mem_type: MemoryType,
    term_ids: list[UUID],
    content: str,
    scope: Scope | None = None,
) -> tuple[Memory, list[GlossaryAssociation]]:
    try:
        new_memory = write_memory(db, ctx, mem_type, content, creator, scope)
        glossary_associations = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, term_ids)
    except Exception:
        db.rollback()
        raise
    return new_memory, list(glossary_associations)


def supersede_memory(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    creator: Creator,
    mem_type: MemoryType,
    content: str,
    scope: Scope | None = None,
) -> tuple[Memory, list[GlossaryAssociation]]:
    current_term_ids = list(
        db.execute(
            select(GlossaryTerm.term_id)
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
    try:
        new_memory = write_memory(db, ctx, mem_type, content, creator, scope, supersedes_id=memory_id)
        new_assocs = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, current_term_ids)
    except Exception:
        db.rollback()
        raise
    return new_memory, new_assocs
