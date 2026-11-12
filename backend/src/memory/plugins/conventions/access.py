"""Shared convention data access beneath user services and agent toolsets.

Functions here apply no caller policy and never commit; callers own permission
checks and the transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, insert, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import AliasedClass

from src.memory.exceptions import ConventionNotFoundException
from src.memory.overlay import visible_rows, workspace_read
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.shadow_models import ShadowConvention
from src.memory.staging import check_workspace, stage_record
from src.memory.types import Creator, ReviewStatus


def read_conventions(
    db: Session,
    memory_group_id: UUID,
    *,
    workspace_id: UUID | None = None,
    category: ConventionCategory | None = None,
    review_statuses: Sequence[ReviewStatus] | None = None,
) -> list[TranslationConvention]:
    """Read a group's conventions in creation order; None filters match everything."""
    convention_rows = visible_rows(TranslationConvention, ShadowConvention, workspace_id)
    statement = select(convention_rows).where(convention_rows.memory_group_id == memory_group_id)
    if category is not None:
        statement = statement.where(convention_rows.category == category)
    if review_statuses is not None:
        statement = statement.where(convention_rows.review_status.in_(review_statuses))
    statement = statement.order_by(convention_rows.created_at, convention_rows.convention_id)
    return list(db.scalars(workspace_read(statement, workspace_id)))


def create_convention(
    db: Session,
    memory_group_id: UUID,
    *,
    category: ConventionCategory,
    title: str,
    rule: str,
    rationale: str | None,
    creator_type: Creator,
    workspace_id: UUID | None = None,
) -> TranslationConvention | ShadowConvention:
    if workspace_id is not None:
        check_workspace(db, workspace_id, memory_group_id)
        return stage_record(
            db,
            ShadowConvention,
            workspace_id,
            memory_group_id=memory_group_id,
            category=category,
            title=title,
            rule=rule,
            rationale=rationale,
            creator_type=creator_type,
        )
    return db.execute(
        insert(TranslationConvention)
        .values(
            memory_group_id=memory_group_id,
            category=category,
            title=title,
            rule=rule,
            rationale=rationale,
            creator_type=creator_type,
        )
        .returning(TranslationConvention)
    ).scalar_one()


def _convention_filters(
    memory_group_id: UUID,
    convention_id: UUID,
    only_creator: Creator | None,
    only_pending: bool,
    convention_rows: type[TranslationConvention] | AliasedClass[TranslationConvention] = TranslationConvention,
) -> list[ColumnElement[bool]]:
    filters = [
        convention_rows.memory_group_id == memory_group_id,
        convention_rows.convention_id == convention_id,
    ]
    if only_creator is not None:
        filters.append(convention_rows.creator_type == only_creator)
    if only_pending:
        filters.append(convention_rows.review_status == ReviewStatus.PENDING)
    return filters


def update_convention(
    db: Session,
    memory_group_id: UUID,
    convention_id: UUID,
    *,
    category: ConventionCategory,
    title: str,
    rule: str,
    rationale: str | None,
    only_creator: Creator | None = None,
    only_pending: bool = False,
    workspace_id: UUID | None = None,
) -> None:
    if workspace_id is not None:
        check_workspace(db, workspace_id, memory_group_id)
        convention_rows = visible_rows(TranslationConvention, ShadowConvention, workspace_id)
        try:
            original = db.scalars(
                workspace_read(
                    select(convention_rows).where(
                        *_convention_filters(
                            memory_group_id, convention_id, only_creator, only_pending, convention_rows
                        )
                    ),
                    workspace_id,
                )
            ).one()
        except NoResultFound as e:
            raise ConventionNotFoundException(f"Convention {convention_id} not found or not editable") from e
        stage_record(
            db, ShadowConvention, workspace_id, original, category=category, title=title, rule=rule, rationale=rationale
        )
        return
    try:
        db.execute(
            update(TranslationConvention)
            .where(*_convention_filters(memory_group_id, convention_id, only_creator, only_pending))
            .values(category=category, title=title, rule=rule, rationale=rationale, updated_at=func.now())
            .returning(TranslationConvention.convention_id)
        ).scalar_one()
    except NoResultFound as e:
        raise ConventionNotFoundException(f"Convention {convention_id} not found or not editable") from e


def delete_convention(
    db: Session,
    memory_group_id: UUID,
    convention_id: UUID,
    *,
    only_creator: Creator | None = None,
    only_pending: bool = False,
    workspace_id: UUID | None = None,
) -> None:
    if workspace_id is not None:
        check_workspace(db, workspace_id, memory_group_id)
        convention_rows = visible_rows(TranslationConvention, ShadowConvention, workspace_id)
        try:
            original = db.scalars(
                workspace_read(
                    select(convention_rows).where(
                        *_convention_filters(
                            memory_group_id, convention_id, only_creator, only_pending, convention_rows
                        )
                    ),
                    workspace_id,
                )
            ).one()
        except NoResultFound as e:
            raise ConventionNotFoundException(f"Convention {convention_id} not found or not editable") from e
        published_id = db.scalar(
            select(TranslationConvention.convention_id).where(
                TranslationConvention.convention_id == convention_id,
                TranslationConvention.memory_group_id == memory_group_id,
            )
        )
        if published_id is None:
            db.execute(
                delete(ShadowConvention).where(
                    ShadowConvention.workspace_id == workspace_id, ShadowConvention.convention_id == convention_id
                )
            )
        else:
            stage_record(db, ShadowConvention, workspace_id, original, deleted=True)
        return
    try:
        db.execute(
            delete(TranslationConvention)
            .where(*_convention_filters(memory_group_id, convention_id, only_creator, only_pending))
            .returning(TranslationConvention.convention_id)
        ).scalar_one()
    except NoResultFound as e:
        raise ConventionNotFoundException(f"Convention {convention_id} not found or not editable") from e
