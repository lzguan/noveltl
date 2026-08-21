from collections.abc import Callable
from typing import Final
from uuid import UUID

from sqlalchemy import SQLColumnExpression, insert, literal, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from src.memory.access import MemAccessContext, check_mem_access_ctx, write_memory
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.models import Memory
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.types import Creator, MemoryType, PluginName, ReviewStatus, Scope
from src.novels.models import ChapterContent

type ContainsQuery = Callable[
    [SQLColumnExpression[str], SQLColumnExpression[str]],
    SQLColumnExpression[bool],
]

GLOSSARY_PLUGIN_NAME: Final[PluginName] = "glossary"


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
    memory_types: list[MemoryType] | None,
    *,
    include_rejected: bool = False,
) -> list[tuple[Memory, list[GlossaryTerm]]]:
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
            Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
        )
        .order_by(Memory.memory_start_num.desc(), Memory.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
    )
    if not include_rejected:
        query = query.where(
            Memory.memory_review_status != ReviewStatus.REJECTED, GlossaryTerm.review_status != ReviewStatus.REJECTED
        )
    if memory_types is not None:
        query = query.where(Memory.memory_type.in_(memory_types))

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
        raise GlossaryTermNotFoundException("A glossary memory must be associated with at least one term.")

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
) -> tuple[Memory, list[GlossaryAssociation]]:
    try:
        new_memory = write_memory(db, ctx, mem_type, content, creator, GLOSSARY_PLUGIN_NAME, scope)
        glossary_associations = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, term_names)
    except Exception:
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
    current_term_names = list(
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
    try:
        new_memory = write_memory(
            db, ctx, mem_type, content, creator, GLOSSARY_PLUGIN_NAME, scope, supersedes_id=memory_id
        )
        new_assocs = _associate_terms(db, ctx.memory_group_id, new_memory.memory_id, current_term_names)
    except Exception:
        raise
    return new_memory, new_assocs
