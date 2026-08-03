"""
Permissions for AutoLabels. These are used to check if a user has permission to perform certain actions on auto labels, such as creating, modifying, or deleting them. The permissions are based on the user's role and their access to the associated label group and novel data.
"""

from typing import Any

from sqlalchemy import Select, exists, select
from sqlalchemy.orm import aliased

from src.auth.constants import UserType
from src.auth.models import User
from src.autolabels.models import AutoLabel
from src.novels import models as novel_models
from src.novels.permissions import chapter_content_mod_access_select


def auto_label_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T,
    current_user: User,
    aliased_type: type[AutoLabel] = AutoLabel,
    *,
    edit_only: bool = False,
    contributor_only: bool = False,
) -> T:
    """
    Modify a select query to check if the current user has permission to modify the auto label.

    Args:
        q: The select query to modify.
        current_user: The user for whom to check permissions.
    """
    subq = (
        select(1)
        .where(aliased_type.chapter_content_id == novel_models.ChapterContent.chapter_content_id)
        .correlate(aliased_type)
    )
    subq = chapter_content_mod_access_select(subq, current_user, edit_only=edit_only)
    if contributor_only and current_user.user_type != UserType.ADMIN:
        chapter_alias = aliased(novel_models.Chapter)
        contributor_alias = aliased(novel_models.NovelContributor)
        subq = subq.where(
            exists(
                select(1)
                .select_from(chapter_alias)
                .join(contributor_alias, contributor_alias.novel_id == chapter_alias.novel_id)
                .where(chapter_alias.chapter_id == novel_models.ChapterContent.chapter_id)
                .where(contributor_alias.user_id == current_user.user_id)
            )
        )
    return q.where(exists(subq))


def auto_label_mod_access_insert[T: Select[tuple[Any, ...]]](
    stmt: T,
    current_user: User,
    *,
    edit_only: bool = False,
    contributor_only: bool = False,
) -> T:
    """
    Modify an insert query to check if the current user has permission to create the auto label. Assumes T selects from novel_models.ChapterContent.

    Args:
        stmt: The insert query to modify.
        current_user: The user for whom to check permissions.
    """
    stmt = chapter_content_mod_access_select(stmt, current_user, edit_only=edit_only)
    if contributor_only and current_user.user_type != UserType.ADMIN:
        chapter_alias = aliased(novel_models.Chapter)
        contributor_alias = aliased(novel_models.NovelContributor)
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(chapter_alias)
                .join(contributor_alias, contributor_alias.novel_id == chapter_alias.novel_id)
                .where(chapter_alias.chapter_id == novel_models.ChapterContent.chapter_id)
                .where(contributor_alias.user_id == current_user.user_id)
            )
        )
    return stmt
