import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, exists, or_, select
from sqlalchemy.orm import aliased

from ..auth.constants import UserType
from ..auth.models import User
from .constants import Role, Visibility
from .models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


def novel_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[Novel] = Novel
) -> T:
    """
    Takes a select statement for novels and returns a select statement that restricts permissions on q.

    Usage:
    ```python
    # without alias
    stmt = select(Novel)
    stmt = novel_mod_access_select(stmt, current_user)

    # with alias
    alias = aliased(Novel)
    stmt = select(alias).where(alias.novel_id == novel_id)
    stmt = novel_mod_access_select(stmt, current_user, alias)
    ```
    """
    nc_alias = aliased(NovelContributor)

    if current_user is None:
        return q.where(aliased_type.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(
            or_(
                aliased_type.novel_visibility >= Visibility.UNLISTED,
                exists(
                    select(1)
                    .select_from(nc_alias)
                    .where(nc_alias.novel_id == aliased_type.novel_id)
                    .where(nc_alias.user_id == current_user.user_id)
                ),
            )
        )
    return q


def novel_mod_access_update[T: Update](stmt: T, current_user: User, aliased_type: type[Novel] = Novel) -> T:
    """
    Takes an update statement for novels and returns an update statement that restricts permissions on stmt.
    """
    nc_alias = aliased(NovelContributor)

    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(nc_alias)
                .where(nc_alias.novel_id == aliased_type.novel_id)
                .where(nc_alias.user_id == current_user.user_id)
                .where(nc_alias.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def source_work_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[SourceWork] = SourceWork
) -> T:
    """
    Takes a select statement for source works and returns a select statement that restricts permissions on source works.
    """
    novel_alias = aliased(Novel)
    subq = (
        select(1)
        .select_from(novel_alias)
        .where(novel_alias.source_work_id == aliased_type.source_work_id)
        .correlate(aliased_type)
    )
    subq = novel_mod_access_select(subq, current_user, novel_alias)
    return q.where(exists(subq))


def source_work_mod_access_update[T: Update](
    stmt: T, current_user: User, aliased_type: type[SourceWork] = SourceWork
) -> T:
    """
    Takes an update statement for source works and returns an update statement that restricts permissions on source works.
    """
    novel_alias = aliased(Novel)
    nc_alias = aliased(NovelContributor)

    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(novel_alias)
                .where(novel_alias.source_work_id == aliased_type.source_work_id)
                .where(
                    exists(
                        select(1)
                        .select_from(nc_alias)
                        .where(nc_alias.novel_id == novel_alias.novel_id)
                        .where(nc_alias.user_id == current_user.user_id)
                        .where(nc_alias.contributor_role.in_([Role.OWNER]))
                    )
                )
            )
        )
    return stmt


def chapter_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[Chapter] = Chapter
) -> T:
    """
    Takes a select statement on chapters and returns a select statement that restricts permissions on chapters.
    """
    novel_alias = aliased(Novel)
    nc_alias = aliased(NovelContributor)

    if current_user is None:
        return q.where(
            exists(
                select(1)
                .select_from(novel_alias)
                .where(novel_alias.novel_id == aliased_type.novel_id)
                .where(novel_alias.novel_visibility >= Visibility.UNLISTED)
                .correlate(aliased_type)
            )
        ).where(aliased_type.chapter_is_public.is_(True))
    elif current_user.user_type != UserType.ADMIN:
        sub_q = (
            select(1)
            .select_from(novel_alias)
            .where(aliased_type.novel_id == novel_alias.novel_id)
            .correlate(aliased_type)
        )
        sub_q = novel_mod_access_select(sub_q, current_user, novel_alias)
        return q.where(exists(sub_q)).where(
            or_(
                aliased_type.chapter_is_public.is_(True),
                exists(
                    select(1)
                    .select_from(nc_alias)
                    .where(nc_alias.novel_id == aliased_type.novel_id)
                    .where(nc_alias.user_id == current_user.user_id)
                ),
            )
        )
    return q


def chapter_mod_access_update[T: Update](stmt: T, current_user: User, aliased_type: type[Chapter] = Chapter) -> T:
    nc_alias = aliased(NovelContributor)
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(nc_alias)
                .where(nc_alias.novel_id == aliased_type.novel_id)
                .where(nc_alias.user_id == current_user.user_id)
                .where(nc_alias.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def chapter_mod_access_insert[T: Select[tuple[Any, ...]]](stmt: T, current_user: User, novel_id: uuid.UUID) -> T:
    """
    Takes an select statement used for an insert from select statement for chapter and returns a select statement for a chapter that restrict permissions on stmt.
    """
    nc_alias = aliased(NovelContributor)
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(nc_alias)
                .where(nc_alias.novel_id == novel_id)
                .where(nc_alias.user_id == current_user.user_id)
                .where(nc_alias.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def chapter_mod_access_delete[T: Delete](stmt: T, current_user: User, aliased_type: type[Chapter] = Chapter) -> T:
    nc_alias = aliased(NovelContributor)
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(nc_alias)
                .where(nc_alias.novel_id == aliased_type.novel_id)
                .where(nc_alias.user_id == current_user.user_id)
                .where(nc_alias.contributor_role == Role.OWNER)
            )
        )
    return stmt


def chapter_content_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[ChapterContent] = ChapterContent
) -> T:
    chapter_alias = aliased(Chapter)
    subq = (
        select(1)
        .select_from(chapter_alias)
        .where(chapter_alias.chapter_id == aliased_type.chapter_id)
        .correlate(aliased_type)
    )
    subq = chapter_mod_access_select(subq, current_user, chapter_alias)
    return q.where(exists(subq))


def chapter_content_mod_access_insert[T: Select[tuple[Any, ...]]](
    stmt: T, current_user: User, chapter_id: uuid.UUID
) -> T:
    nc_alias = aliased(NovelContributor)
    chapter_alias = aliased(Chapter)
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(nc_alias)
                .where(
                    nc_alias.novel_id
                    == select(chapter_alias.novel_id).where(chapter_alias.chapter_id == chapter_id).scalar_subquery()
                )
                .where(nc_alias.user_id == current_user.user_id)
                .where(nc_alias.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt
