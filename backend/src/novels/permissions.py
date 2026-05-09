import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, exists, or_, select

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
    if current_user is None:
        return q.where(aliased_type.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(
            or_(
                aliased_type.novel_visibility >= Visibility.UNLISTED,
                exists(
                    select(1)
                    .select_from(NovelContributor)
                    .where(NovelContributor.novel_id == aliased_type.novel_id)
                    .where(NovelContributor.user_id == current_user.user_id)
                ),
            )
        )
    return q


def novel_mod_access_update[T: Update](stmt: T, current_user: User) -> T:
    """
    Takes an update statement for novels and returns an update statement that restricts permissions on stmt.
    """
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(NovelContributor)
                .where(NovelContributor.novel_id == Novel.novel_id)
                .where(NovelContributor.user_id == current_user.user_id)
                .where(NovelContributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def source_work_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[SourceWork] = SourceWork
) -> T:
    """
    Takes a select statement for source works and returns a select statement that restricts permissions on source works.
    """
    subq = (
        select(1).select_from(Novel).where(Novel.source_work_id == aliased_type.source_work_id).correlate(aliased_type)
    )
    subq = novel_mod_access_select(subq, current_user)
    return q.where(exists(subq))


def source_work_mod_access_update[T: Update](stmt: T, current_user: User) -> T:
    """
    Takes an update statement for source works and returns an update statement that restricts permissions on source works.
    """
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(Novel)
                .where(Novel.source_work_id == SourceWork.source_work_id)
                .where(
                    exists(
                        select(1)
                        .select_from(NovelContributor)
                        .where(NovelContributor.novel_id == Novel.novel_id)
                        .where(NovelContributor.user_id == current_user.user_id)
                        .where(NovelContributor.contributor_role.in_([Role.OWNER]))
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
    if current_user is None:
        return q.where(
            exists(
                select(1)
                .select_from(Novel)
                .where(Novel.novel_id == aliased_type.novel_id)
                .where(Novel.novel_visibility >= Visibility.UNLISTED)
                .correlate(aliased_type)
            )
        ).where(aliased_type.chapter_is_public.is_(True))
    elif current_user.user_type != UserType.ADMIN:
        sub_q = select(1).select_from(Novel).where(aliased_type.novel_id == Novel.novel_id).correlate(aliased_type)
        sub_q = novel_mod_access_select(sub_q, current_user)
        return q.where(exists(sub_q)).where(
            or_(
                aliased_type.chapter_is_public.is_(True),
                exists(
                    select(1)
                    .select_from(NovelContributor)
                    .where(NovelContributor.novel_id == aliased_type.novel_id)
                    .where(NovelContributor.user_id == current_user.user_id)
                ),
            )
        )
    return q


def chapter_mod_access_update[T: Update](stmt: T, current_user: User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(NovelContributor)
                .where(NovelContributor.novel_id == Chapter.novel_id)
                .where(NovelContributor.user_id == current_user.user_id)
                .where(NovelContributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def chapter_mod_access_insert[T: Select[tuple[Any, ...]]](stmt: T, current_user: User, novel_id: uuid.UUID) -> T:
    """
    Takes an select statement used for an insert from select statement for chapter and returns a select statement for a chapter that restrict permissions on stmt.
    """
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(NovelContributor)
                .where(NovelContributor.novel_id == novel_id)
                .where(NovelContributor.user_id == current_user.user_id)
                .where(NovelContributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt


def chapter_mod_access_delete[T: Delete](stmt: T, current_user: User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(NovelContributor)
                .where(NovelContributor.novel_id == Chapter.novel_id)
                .where(NovelContributor.user_id == current_user.user_id)
                .where(NovelContributor.contributor_role == Role.OWNER)
            )
        )
    return stmt


def chapter_content_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User | None, aliased_type: type[ChapterContent] = ChapterContent
) -> T:
    subq = select(1).select_from(Chapter).where(Chapter.chapter_id == aliased_type.chapter_id).correlate(aliased_type)
    subq = chapter_mod_access_select(subq, current_user)
    return q.where(exists(subq))


def chapter_content_mod_access_insert[T: Select[tuple[Any, ...]]](
    stmt: T, current_user: User, chapter_id: uuid.UUID
) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1)
                .select_from(NovelContributor)
                .where(
                    NovelContributor.novel_id
                    == select(Chapter.novel_id).where(Chapter.chapter_id == chapter_id).scalar_subquery()
                )
                .where(NovelContributor.user_id == current_user.user_id)
                .where(NovelContributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt
