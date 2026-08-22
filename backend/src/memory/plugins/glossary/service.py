from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory import service as memory_service
from src.memory.access import MemAccessContext
from src.memory.exceptions import (
    GlossaryTermAlreadyExistsException,
    GlossaryTermNotFoundException,
    MemoryGroupNotFoundException,
    MemoryNotFoundException,
)
from src.memory.models import Memory, MemoryGroup
from src.memory.permissions import memory_group_mod_access_select, memory_mod_access_select
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.access import GLOSSARY_PLUGIN_NAME
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.permissions import (
    glossary_term_mod_access_delete,
    glossary_term_mod_access_select,
    glossary_term_mod_access_update,
)
from src.memory.plugins.glossary.schemas import (
    GlossaryMemory,
    GlossaryMemoryPage,
    GlossaryTermPage,
)
from src.memory.schemas import Memory as MemorySchema
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope


def _query_editable_group(db: Session, user: User, memory_group_id: UUID) -> MemoryGroup:
    query = memory_group_mod_access_select(
        select(MemoryGroup).where(MemoryGroup.memory_group_id == memory_group_id),
        user,
        edit_only=True,
    )
    try:
        return db.execute(query).scalar_one()
    except NoResultFound as e:
        raise MemoryGroupNotFoundException from e


def _enrich_memories(db: Session, memories: list[Memory], count: int) -> GlossaryMemoryPage:
    memory_ids = [memory.memory_id for memory in memories]
    terms_by_memory: dict[UUID, list[GlossaryTerm]] = {memory_id: [] for memory_id in memory_ids}
    if memory_ids:
        rows = db.execute(
            select(GlossaryAssociation.memory_id, GlossaryTerm)
            .join(GlossaryTerm, GlossaryTerm.term_id == GlossaryAssociation.term_id)
            .where(GlossaryAssociation.memory_id.in_(memory_ids))
            .order_by(GlossaryAssociation.memory_id, GlossaryTerm.term, GlossaryTerm.term_id)
        ).all()
        for memory_id, term in rows:
            terms_by_memory[memory_id].append(term)
    return GlossaryMemoryPage(
        count=count,
        rows=[
            GlossaryMemory(
                memory=MemorySchema.model_validate(memory),
                terms=terms_by_memory[memory.memory_id],
            )
            for memory in memories
        ],
    )


def query_glossary_memories_at_chapter(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    chapter_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    created_exactly_at_chapter: bool = False,
    memory_types: list[MemoryType] | None = None,
) -> GlossaryMemoryPage:
    page = memory_service.query_memories_at_chapter(
        db,
        user,
        memory_group_id,
        chapter_id,
        skip,
        limit,
        created_exactly_at_chapter=created_exactly_at_chapter,
        plugin_names=[GLOSSARY_PLUGIN_NAME],
        memory_types=memory_types,
    )
    return _enrich_memories(db, page.rows, page.count)


def query_glossary_memories(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    memory_types: list[MemoryType] | None = None,
) -> GlossaryMemoryPage:
    page = memory_service.query_memories(
        db,
        user,
        memory_group_id,
        skip,
        limit,
        plugin_names=[GLOSSARY_PLUGIN_NAME],
        memory_types=memory_types,
    )
    return _enrich_memories(db, page.rows, page.count)


def query_glossary_terms(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    search: str | None = None,
    review_statuses: list[ReviewStatus] | None = None,
) -> GlossaryTermPage:
    def apply_filters(query):
        query = query.where(GlossaryTerm.memory_group_id == memory_group_id)
        query = glossary_term_mod_access_select(query, user)
        if search is not None:
            query = query.where(GlossaryTerm.term.contains(search))
        if review_statuses is not None:
            query = query.where(GlossaryTerm.review_status.in_(review_statuses))
        return query

    count = db.execute(apply_filters(select(func.count(GlossaryTerm.term_id)))).scalar_one()
    terms = list(
        db.scalars(
            apply_filters(select(GlossaryTerm))
            .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
            .offset(skip)
            .limit(limit)
        ).all()
    )
    return GlossaryTermPage(count=count, rows=terms)


def query_memories_for_term(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    term_id: UUID,
    skip: int = 0,
    limit: int = 100,
) -> GlossaryMemoryPage:
    term_query = glossary_term_mod_access_select(
        select(GlossaryTerm).where(
            GlossaryTerm.term_id == term_id,
            GlossaryTerm.memory_group_id == memory_group_id,
        ),
        user,
    )
    try:
        db.execute(term_query).scalar_one()
    except NoResultFound as e:
        raise GlossaryTermNotFoundException from e

    def apply_filters(query):
        query = (
            query.select_from(Memory)
            .join(GlossaryAssociation, GlossaryAssociation.memory_id == Memory.memory_id)
            .where(
                GlossaryAssociation.term_id == term_id,
                Memory.memory_group_id == memory_group_id,
                Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
            )
        )
        return memory_mod_access_select(query, user)

    count = db.execute(apply_filters(select(func.count(Memory.memory_id)))).scalar_one()
    memories = list(
        db.scalars(
            apply_filters(select(Memory))
            .order_by(Memory.memory_start_num.desc(), Memory.memory_id)
            .offset(skip)
            .limit(limit)
        ).all()
    )
    return _enrich_memories(db, memories, count)


def query_terms_for_memory(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    memory_id: UUID,
) -> list[GlossaryTerm]:
    memory_query = memory_mod_access_select(
        select(Memory).where(
            Memory.memory_id == memory_id,
            Memory.memory_group_id == memory_group_id,
            Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
        ),
        user,
    )
    try:
        db.execute(memory_query).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException from e
    return list(
        db.scalars(
            select(GlossaryTerm)
            .join(GlossaryAssociation, GlossaryAssociation.term_id == GlossaryTerm.term_id)
            .where(GlossaryAssociation.memory_id == memory_id)
            .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
        ).all()
    )


def create_glossary_memory(
    db: Session,
    user: User,
    memory_group_id: UUID,
    chapter_id: UUID,
    chapter_content_id: UUID,
    memory_type: MemoryType,
    memory_content: str,
    term_ids: list[UUID],
    scope: Scope | None = None,
) -> GlossaryMemory:
    _query_editable_group(db, user, memory_group_id)
    unique_term_ids = list(dict.fromkeys(term_ids))
    terms = list(
        db.scalars(
            select(GlossaryTerm)
            .where(
                GlossaryTerm.memory_group_id == memory_group_id,
                GlossaryTerm.term_id.in_(unique_term_ids),
            )
            .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
        ).all()
    )
    if not unique_term_ids or len(terms) != len(unique_term_ids):
        raise GlossaryTermNotFoundException
    context = MemAccessContext(
        memory_group_id=memory_group_id,
        chapter_id=chapter_id,
        chapter_content_id=chapter_content_id,
    )
    try:
        memory, _ = access.create_memory(
            db,
            context,
            Creator.USER,
            memory_type,
            [term.term for term in terms],
            memory_content,
            scope,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return GlossaryMemory(memory=MemorySchema.model_validate(memory), terms=terms)


def create_glossary_term(db: Session, user: User, memory_group_id: UUID, term: str) -> GlossaryTerm:
    _query_editable_group(db, user, memory_group_id)
    try:
        glossary_term = access.create_term(db, memory_group_id, term)
        db.commit()
        return glossary_term
    except IntegrityError as e:
        db.rollback()
        raise GlossaryTermAlreadyExistsException from e
    except Exception:
        db.rollback()
        raise


def update_glossary_term(
    db: Session,
    user: User,
    memory_group_id: UUID,
    term_id: UUID,
    term: str,
) -> GlossaryTerm:
    query = (
        update(GlossaryTerm)
        .where(GlossaryTerm.term_id == term_id, GlossaryTerm.memory_group_id == memory_group_id)
        .values(term=term)
        .returning(GlossaryTerm)
    )
    query = glossary_term_mod_access_update(query, user)
    try:
        glossary_term = db.execute(query).scalar_one()
        db.commit()
        return glossary_term
    except NoResultFound as e:
        db.rollback()
        raise GlossaryTermNotFoundException from e
    except IntegrityError as e:
        db.rollback()
        raise GlossaryTermAlreadyExistsException from e
    except Exception:
        db.rollback()
        raise


def change_glossary_term_review_status(
    db: Session,
    user: User,
    memory_group_id: UUID,
    term_id: UUID,
    review_status: ReviewStatus,
) -> GlossaryTerm:
    query = (
        update(GlossaryTerm)
        .where(GlossaryTerm.term_id == term_id, GlossaryTerm.memory_group_id == memory_group_id)
        .values(review_status=review_status)
        .returning(GlossaryTerm)
    )
    query = glossary_term_mod_access_update(query, user)
    try:
        glossary_term = db.execute(query).scalar_one()
        db.commit()
        return glossary_term
    except NoResultFound as e:
        db.rollback()
        raise GlossaryTermNotFoundException from e
    except Exception:
        db.rollback()
        raise


def replace_memory_terms(
    db: Session,
    user: User,
    memory_group_id: UUID,
    memory_id: UUID,
    term_ids: list[UUID],
) -> list[GlossaryTerm]:
    memory_query = memory_mod_access_select(
        select(Memory).where(
            Memory.memory_id == memory_id,
            Memory.memory_group_id == memory_group_id,
            Memory.plugin_name == GLOSSARY_PLUGIN_NAME,
        ),
        user,
        edit_only=True,
    )
    try:
        db.execute(memory_query).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException from e

    unique_term_ids = list(dict.fromkeys(term_ids))
    terms = list(
        db.scalars(
            glossary_term_mod_access_select(
                select(GlossaryTerm).where(
                    GlossaryTerm.memory_group_id == memory_group_id,
                    GlossaryTerm.term_id.in_(unique_term_ids),
                ),
                user,
                edit_only=True,
            ).order_by(GlossaryTerm.term, GlossaryTerm.term_id)
        ).all()
    )
    if len(terms) != len(unique_term_ids):
        raise GlossaryTermNotFoundException
    try:
        db.execute(delete(GlossaryAssociation).where(GlossaryAssociation.memory_id == memory_id))
        db.add_all([GlossaryAssociation(memory_id=memory_id, term_id=term.term_id) for term in terms])
        db.commit()
        return terms
    except Exception:
        db.rollback()
        raise


def delete_glossary_term(db: Session, user: User, memory_group_id: UUID, term_id: UUID) -> UUID:
    query = (
        delete(GlossaryTerm)
        .where(GlossaryTerm.term_id == term_id, GlossaryTerm.memory_group_id == memory_group_id)
        .returning(GlossaryTerm.term_id)
    )
    query = glossary_term_mod_access_delete(query, user)
    try:
        deleted_term_id = db.execute(query).scalar_one()
        db.commit()
        return deleted_term_id
    except NoResultFound as e:
        db.rollback()
        raise GlossaryTermNotFoundException from e
    except Exception:
        db.rollback()
        raise
