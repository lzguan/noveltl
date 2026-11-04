"""Permission-aware convention reads and manual edits."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory.exceptions import ConventionNotFoundException, MemoryGroupNotFoundException
from src.memory.models import MemoryGroup
from src.memory.permissions import memory_group_mod_access_select
from src.memory.plugins.conventions import access
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.permissions import (
    convention_mod_access_delete,
    convention_mod_access_select,
    convention_mod_access_update,
)
from src.memory.plugins.conventions.schemas import ConventionPage, ConventionRead, SaveConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus


def query_conventions(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    category: ConventionCategory | None = None,
    review_statuses: list[ReviewStatus] | None = None,
) -> ConventionPage:
    """Read a group's conventions, including rejected ones unless filtered out."""

    def build_query[T: Select[*tuple[Any, ...]]](base: T) -> T:
        query = base.where(TranslationConvention.memory_group_id == memory_group_id)
        query = convention_mod_access_select(query, user)
        if category is not None:
            query = query.where(TranslationConvention.category == category)
        if review_statuses is not None:
            query = query.where(TranslationConvention.review_status.in_(review_statuses))
        return query

    rows = db.scalars(
        build_query(select(TranslationConvention))
        .order_by(TranslationConvention.created_at, TranslationConvention.convention_id)
        .offset(skip)
        .limit(limit)
    )
    return ConventionPage(
        count=db.execute(build_query(select(func.count(TranslationConvention.convention_id)))).scalar_one(),
        rows=[ConventionRead.model_validate(row) for row in rows],
    )


def create_convention(db: Session, user: User, memory_group_id: UUID, request: SaveConvention) -> ConventionRead:
    group_query = select(MemoryGroup.memory_group_id).where(MemoryGroup.memory_group_id == memory_group_id)
    group_query = memory_group_mod_access_select(group_query, user, edit_only=True)
    if db.execute(group_query).scalar_one_or_none() is None:
        raise MemoryGroupNotFoundException
    try:
        row = access.create_convention(
            db,
            memory_group_id,
            category=request.category,
            title=request.title,
            rule=request.rule,
            rationale=request.rationale,
            creator_type=Creator.USER,
        )
        result = ConventionRead.model_validate(row)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def update_convention(
    db: Session, user: User, memory_group_id: UUID, convention_id: UUID, request: SaveConvention
) -> ConventionRead:
    """Replace a convention's content; a manual edit makes the user its creator."""
    query = (
        update(TranslationConvention)
        .where(
            TranslationConvention.memory_group_id == memory_group_id,
            TranslationConvention.convention_id == convention_id,
        )
        .values(
            category=request.category,
            title=request.title,
            rule=request.rule,
            rationale=request.rationale,
            creator_type=Creator.USER,
            updated_at=func.now(),
        )
        .returning(TranslationConvention)
    )
    query = convention_mod_access_update(query, user)
    try:
        result = ConventionRead.model_validate(
            db.execute(query, execution_options={"populate_existing": True}).scalar_one()
        )
        db.commit()
        return result
    except NoResultFound as e:
        db.rollback()
        raise ConventionNotFoundException from e
    except Exception:
        db.rollback()
        raise


def change_convention_review_status(
    db: Session, user: User, memory_group_id: UUID, convention_id: UUID, review_status: ReviewStatus
) -> ConventionRead:
    query = (
        update(TranslationConvention)
        .where(
            TranslationConvention.memory_group_id == memory_group_id,
            TranslationConvention.convention_id == convention_id,
        )
        .values(review_status=review_status, updated_at=func.now())
        .returning(TranslationConvention)
    )
    query = convention_mod_access_update(query, user)
    try:
        result = ConventionRead.model_validate(
            db.execute(query, execution_options={"populate_existing": True}).scalar_one()
        )
        db.commit()
        return result
    except NoResultFound as e:
        db.rollback()
        raise ConventionNotFoundException from e
    except Exception:
        db.rollback()
        raise


def delete_convention(db: Session, user: User, memory_group_id: UUID, convention_id: UUID) -> None:
    query = (
        delete(TranslationConvention)
        .where(
            TranslationConvention.memory_group_id == memory_group_id,
            TranslationConvention.convention_id == convention_id,
        )
        .returning(TranslationConvention.convention_id)
    )
    query = convention_mod_access_delete(query, user)
    try:
        db.execute(query).scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise ConventionNotFoundException from e
    except Exception:
        db.rollback()
        raise
