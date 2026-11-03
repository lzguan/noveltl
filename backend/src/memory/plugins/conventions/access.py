"""Shared convention data access beneath user services and agent toolsets.

Functions here apply no caller policy and never commit; callers own permission
checks and the transaction.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus


def read_conventions(
    db: Session,
    memory_group_id: UUID,
    *,
    category: ConventionCategory | None = None,
    review_statuses: Sequence[ReviewStatus] | None = None,
) -> list[TranslationConvention]:
    """Read a group's conventions in creation order; None filters match everything."""
    statement = select(TranslationConvention).where(TranslationConvention.memory_group_id == memory_group_id)
    if category is not None:
        statement = statement.where(TranslationConvention.category == category)
    if review_statuses is not None:
        statement = statement.where(TranslationConvention.review_status.in_(review_statuses))
    statement = statement.order_by(TranslationConvention.created_at, TranslationConvention.convention_id)
    return list(db.scalars(statement))


def create_convention(
    db: Session,
    memory_group_id: UUID,
    *,
    category: ConventionCategory,
    title: str,
    rule: str,
    rationale: str | None,
    creator_type: Creator,
) -> TranslationConvention:
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
