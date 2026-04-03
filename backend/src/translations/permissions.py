"""
Module for putting permission restrictions on database queries for novel translation jobs.
"""

import uuid
from typing import Any

from sqlalchemy import Select, exists, select

from ..auth.constants import UserType
from ..auth.models import User
from ..novels.constants import Role
from ..novels.models import Contributor
from .models import NovelTranslationJob


def novel_translation_job_mod_access_select[T: Select[tuple[Any, ...]]](q: T, current_user: User) -> T:
    """
    Takes a select statement for novel translation jobs and restricts to jobs
    where the current user is a contributor to the source novel.

    Admin: no restriction.
    Regular user: must be a contributor (any role) to the source novel.
    """
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(Contributor)
                .where(Contributor.novel_id == NovelTranslationJob.source_novel_id)
                .where(Contributor.user_id == current_user.user_id)
            )
        )
    return q


def novel_translation_job_mod_access_insert[T: Select[tuple[Any, ...]]](
    q: T, current_user: User, source_novel_id: uuid.UUID
) -> T:
    """
    Takes a select statement used for an insert-from-select for novel translation jobs
    and restricts permissions to require contributor (owner/editor) access to the source novel.
    """
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(Contributor)
                .where(Contributor.novel_id == source_novel_id)
                .where(Contributor.user_id == current_user.user_id)
                .where(Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return q
