from uuid import UUID

from sqlalchemy import insert, literal, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext, check_mem_access_ctx, write_memory
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.models import Memory
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope


def inspect_terms(
    db: Session,
    ctx: MemAccessContext,
    term_ids: list[UUID],
    *,
    include_rejected: bool = False,
) -> list[Memory]:
    chap_num, _ = check_mem_access_ctx(db, ctx)
    query = (
        select(Memory)
        .select_from(GlossaryTerm)
        .where(
            GlossaryTerm.term_id.in_(term_ids),
            GlossaryTerm.memory_group_id == ctx.memory_group_id,
        )
        .join(GlossaryAssociation, GlossaryAssociation.term_id == GlossaryTerm.term_id)
        .join(Memory, Memory.memory_id == GlossaryAssociation.memory_id)
        .where(
            Memory.memory_group_id == ctx.memory_group_id,
            Memory.memory_start_num <= chap_num,
            or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chap_num),
        )
        .order_by(Memory.memory_start_num.desc())
    )
    if not include_rejected:
        query = query.where(Memory.memory_review_status != ReviewStatus.REJECTED)

    memories = (
        db.execute(query)
        .scalars()
        .unique()
        .all()
    )
    return list(memories)


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
