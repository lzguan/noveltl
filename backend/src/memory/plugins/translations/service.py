"""Permission-aware translation reads and manual edits."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory.exceptions import (
    GlossaryTermNotFoundException,
    MemoryGroupNotFoundException,
    TermTranslationNotFoundException,
)
from src.memory.models import MemoryGroup
from src.memory.permissions import memory_group_mod_access_select
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.permissions import glossary_term_mod_access_select
from src.memory.plugins.translations.models import TermTranslation
from src.memory.plugins.translations.schemas import TermTranslationRead
from src.memory.types import Creator, ReviewStatus


def query_term_translations(
    db: Session, user: User | None, memory_group_id: UUID, term_ids: Sequence[UUID]
) -> list[TermTranslationRead]:
    group = memory_group_mod_access_select(
        select(MemoryGroup.memory_group_id).where(MemoryGroup.memory_group_id == memory_group_id), user
    )
    if db.scalar(group) is None:
        raise MemoryGroupNotFoundException
    statement = (
        select(TermTranslation)
        .join(GlossaryTerm, GlossaryTerm.term_id == TermTranslation.term_id)
        .where(GlossaryTerm.memory_group_id == memory_group_id, GlossaryTerm.term_id.in_(term_ids))
        .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
    )
    # The review UI must see rejected mappings as well as usable ones.
    return [TermTranslationRead.model_validate(row) for row in db.scalars(statement)]


def save_term_translation(
    db: Session, user: User, memory_group_id: UUID, term_id: UUID, translation: str
) -> TermTranslationRead:
    term = glossary_term_mod_access_select(
        select(GlossaryTerm.term_id).where(
            GlossaryTerm.memory_group_id == memory_group_id, GlossaryTerm.term_id == term_id
        ),
        user,
        edit_only=True,
    )
    if db.scalar(term) is None:
        raise GlossaryTermNotFoundException
    statement = insert(TermTranslation).values(
        term_id=term_id, translation=translation, creator_type=Creator.USER, review_status=ReviewStatus.PENDING
    )
    statement = statement.on_conflict_do_update(
        index_elements=[TermTranslation.term_id],
        set_={"translation": statement.excluded.translation, "creator_type": Creator.USER, "updated_at": func.now()},
    ).returning(TermTranslation)
    try:
        row = db.scalars(statement, execution_options={"populate_existing": True}).one()
        result = TermTranslationRead.model_validate(row)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def change_term_translation_review_status(
    db: Session, user: User, memory_group_id: UUID, term_id: UUID, review_status: ReviewStatus
) -> TermTranslationRead:
    editable_term = glossary_term_mod_access_select(
        select(GlossaryTerm.term_id).where(
            GlossaryTerm.memory_group_id == memory_group_id, GlossaryTerm.term_id == term_id
        ),
        user,
        edit_only=True,
    )
    statement = (
        update(TermTranslation)
        .where(TermTranslation.term_id.in_(editable_term))
        .values(review_status=review_status)
        .returning(TermTranslation)
    )
    try:
        row = db.scalars(statement, execution_options={"populate_existing": True}).one_or_none()
        if row is None:
            raise TermTranslationNotFoundException
        result = TermTranslationRead.model_validate(row)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def delete_term_translation(db: Session, user: User, memory_group_id: UUID, term_id: UUID) -> None:
    editable_term = glossary_term_mod_access_select(
        select(GlossaryTerm.term_id).where(
            GlossaryTerm.memory_group_id == memory_group_id, GlossaryTerm.term_id == term_id
        ),
        user,
        edit_only=True,
    )
    statement = (
        delete(TermTranslation).where(TermTranslation.term_id.in_(editable_term)).returning(TermTranslation.term_id)
    )
    try:
        if db.scalar(statement) is None:
            raise TermTranslationNotFoundException
        db.commit()
    except Exception:
        db.rollback()
        raise
