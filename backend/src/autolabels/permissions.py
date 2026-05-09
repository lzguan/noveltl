"""
Permissions for AutoLabels. These are used to check if a user has permission to perform certain actions on auto labels, such as creating, modifying, or deleting them. The permissions are based on the user's role and their access to the associated label group and novel data.
"""

from typing import Any

from sqlalchemy import Select, exists, select

from ..auth.models import User
from ..novels import models as novel_models
from ..novels.permissions import chapter_content_mod_access_select
from .models import AutoLabel


def auto_label_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User, aliased_type: type[AutoLabel] = AutoLabel
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
    subq = chapter_content_mod_access_select(subq, current_user)
    return q.where(exists(subq))


def auto_label_mod_access_insert[T: Select[tuple[Any, ...]]](stmt: T, current_user: User) -> T:
    """
    Modify an insert query to check if the current user has permission to create the auto label. Assumes T selects from novel_models.ChapterContent.

    Args:
        stmt: The insert query to modify.
        current_user: The user for whom to check permissions.
    """
    return chapter_content_mod_access_select(stmt, current_user)
