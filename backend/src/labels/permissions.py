"""
Module for putting permission restrictions on database queries.

If a function from this module is called, the permissions on the novel are automatically restricted as well. As of right now, the permissions on the novel/revision are checked only by whether the current user can view it.
"""

import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, and_, exists, literal, or_, select
from sqlalchemy.orm import aliased

from ..auth.constants import UserType
from ..auth.models import User
from ..novels import models as novel_models
from ..novels.constants import Visibility
from ..novels.permissions import chapter_content_mod_access_select, novel_mod_access_select
from .constants import LabelRole
from .models import Label, LabelContributor, LabelData, LabelGroup


def label_group_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User, only_editors: bool = False, aliased_type: type[LabelGroup] = LabelGroup
) -> T:
    """
    Takes a select statement for label groups and returns a select statement that restricts permissions on q.
    """
    novel_alias = aliased(novel_models.Novel)
    lc_alias = aliased(LabelContributor)

    q_exists_novel = (
        select(novel_alias.novel_id).where(novel_alias.novel_id == aliased_type.novel_id).correlate(aliased_type)
    )
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user, novel_alias)
    q = q.where(exists(q_exists_novel))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(lc_alias)
                .where(
                    and_(
                        lc_alias.label_group_id == aliased_type.label_group_id,
                        lc_alias.user_id == current_user.user_id,
                        or_(
                            literal(only_editors is False),
                            lc_alias.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR]),
                        ),
                    )
                )
            )
        )
    return q


def label_group_mod_access_insert[T: Select[tuple[Any, ...]]](q: T, current_user: User, novel_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert statement for label groups and returns a select statement that restricts permissions on q.
    """
    novel_alias = aliased(novel_models.Novel)
    q_exists_novel = select(novel_alias.novel_id).where(novel_alias.novel_id == novel_id)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user, novel_alias)
    q = q.where(exists(q_exists_novel))
    return q


def label_group_mod_access_update[T: Update](
    q: T, current_user: User, aliased_type: type[LabelGroup] = LabelGroup
) -> T:
    """
    Takes an update statement for label groups and returns an update statement that restricts permissions on q.
    """
    novel_alias = aliased(novel_models.Novel)
    lc_alias = aliased(LabelContributor)

    q_exists_novel = (
        select(novel_alias.novel_id).where(novel_alias.novel_id == aliased_type.novel_id).correlate(aliased_type)
    )
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user, novel_alias)
    q = q.where(exists(q_exists_novel))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(lc_alias)
                .where(
                    and_(
                        lc_alias.label_group_id == aliased_type.label_group_id,
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR]),
                    )
                )
            )
        )
    return q


def label_data_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User, aliased_type: type[LabelData] = LabelData
) -> T:
    """
    Takes a select statement for label datas and returns a select statement that restricts permissions on q.
    """
    cc_alias = aliased(novel_models.ChapterContent)
    lc_alias = aliased(LabelContributor)

    q_exists_chapter_content = (
        select(cc_alias.chapter_content_id)
        .where(cc_alias.chapter_content_id == aliased_type.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user, cc_alias)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(lc_alias)
                .where(
                    and_(
                        lc_alias.label_group_id == aliased_type.label_group_id,
                        lc_alias.user_id == current_user.user_id,
                    )
                )
            )
        )
    return q


def label_data_mod_access_update[T: Update](q: T, current_user: User, aliased_type: type[LabelData] = LabelData) -> T:
    """
    Takes an update statement for label datas and returns an update statement that restricts permissions on q.
    """
    cc_alias = aliased(novel_models.ChapterContent)
    lc_alias = aliased(LabelContributor)

    q_exists_chapter_content = (
        select(cc_alias.chapter_content_id)
        .where(cc_alias.chapter_content_id == aliased_type.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user, cc_alias)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(lc_alias)
                .where(
                    and_(
                        lc_alias.label_group_id == aliased_type.label_group_id,
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR]),
                    )
                )
            )
        )
    return q


def label_data_mod_access_insert[T: Select[tuple[Any, ...]]](q: T, current_user: User, label_group_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for label datas and returns a select statement for a label data that restricts permissions on q.

    As of right now, this function grants permissions to insert label datas if the user has edit permissions on the label group and has permission to view the public chapters of the corresponding novel. This may create more label datas for the user than intended, but other permission filters restrict view access to the label datas inserted for revisions the user doesn't have access to, so this is not a security issue. This is done this way because it's difficult to restrict permissions on insert from select statements without introducing extra parameters, which hampers flexibility. STC.
    """
    lc_alias = aliased(LabelContributor)
    lg_alias = aliased(LabelGroup)
    novel_alias = aliased(novel_models.Novel)
    nc_alias = aliased(novel_models.NovelContributor)

    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(lc_alias)
                .where(
                    and_(
                        lc_alias.label_group_id == label_group_id,
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR]),
                    )
                )
            )
        ).where(
            or_(
                exists(
                    select(1)
                    .select_from(lg_alias)
                    .where(lg_alias.label_group_id == label_group_id)
                    .join(novel_alias, lg_alias.novel_id == novel_alias.novel_id)
                    .join(
                        nc_alias,
                        nc_alias.novel_id == novel_alias.novel_id,
                    )
                    .where(nc_alias.user_id == current_user.user_id)
                ),
                select(novel_alias.novel_visibility)
                .select_from(lg_alias)
                .where(lg_alias.label_group_id == label_group_id)
                .join(novel_alias, lg_alias.novel_id == novel_alias.novel_id)
                .scalar_subquery()
                >= Visibility.UNLISTED,
            )
        )
    return q


def label_mod_access_insert[T: Select[tuple[Any, ...]]](q: T, current_user: User, label_data_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for labels and returns a select statement for a label that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    cc_alias = aliased(novel_models.ChapterContent)
    lg_alias = aliased(LabelGroup)
    lc_alias = aliased(LabelContributor)

    q_exists_chapter_content = (
        select(1)
        .select_from(ld_alias)
        .where(ld_alias.label_data_id == label_data_id)
        .join(cc_alias, cc_alias.chapter_content_id == ld_alias.chapter_content_id)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user, cc_alias)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(ld_alias)
                .where(ld_alias.label_data_id == label_data_id)
                .join(lg_alias, ld_alias.label_group_id == lg_alias.label_group_id)
                .join(lc_alias, lg_alias.label_group_id == lc_alias.label_group_id)
                .where(
                    and_(
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER]),
                    )
                )
            )
        )
    return q


def label_mod_access_update[T: Update](q: T, current_user: User, aliased_type: type[Label] = Label) -> T:
    """
    Takes an update statement for labels and returns an update statement that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    cc_alias = aliased(novel_models.ChapterContent)
    lc_alias = aliased(LabelContributor)
    lg_alias = aliased(LabelGroup)

    q_exists_chapter_content = (
        select(1)
        .select_from(ld_alias)
        .where(
            ld_alias.label_data_id == aliased_type.label_data_id  # Correlates to outer Label
        )
        .join(cc_alias, ld_alias.chapter_content_id == cc_alias.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user, cc_alias)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(ld_alias)
                .where(ld_alias.label_data_id == aliased_type.label_data_id)
                .join(lg_alias, ld_alias.label_group_id == lg_alias.label_group_id)
                .join(lc_alias, lg_alias.label_group_id == lc_alias.label_group_id)
                .where(
                    and_(
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER]),
                    )
                )
            )
        )
    return q


def label_mod_access_delete[T: Delete](q: T, current_user: User, aliased_type: type[Label] = Label) -> T:
    """
    Takes a delete statement for labels and returns a delete statement that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    cc_alias = aliased(novel_models.ChapterContent)
    lc_alias = aliased(LabelContributor)
    lg_alias = aliased(LabelGroup)

    q_exists_chapter_content = (
        select(1)
        .select_from(ld_alias)
        .where(
            ld_alias.label_data_id == aliased_type.label_data_id  # Correlates to outer Label
        )
        .join(cc_alias, ld_alias.chapter_content_id == cc_alias.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user, cc_alias)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(1)
                .select_from(ld_alias)
                .where(ld_alias.label_data_id == aliased_type.label_data_id)
                .join(lg_alias, ld_alias.label_group_id == lg_alias.label_group_id)
                .join(lc_alias, lg_alias.label_group_id == lc_alias.label_group_id)
                .where(
                    and_(
                        lc_alias.user_id == current_user.user_id,
                        lc_alias.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER]),
                    )
                )
            )
        )
    return q


def label_contributors_mod_access_select[T: Select[tuple[Any, ...]]](
    q: T, current_user: User, aliased_type: type[LabelContributor] = LabelContributor
) -> T:
    """
    Takes a select statement for label contributors and returns a select statement that restricts permissions on q.
    """
    # as long as the user has view access to the label group, they can see the contributors, so we check permissions based on the label group
    if current_user.user_type != UserType.ADMIN:
        temp_t = aliased(LabelContributor)
        return q.where(
            exists(
                select(1)
                .select_from(temp_t)
                .where(
                    and_(
                        temp_t.label_group_id == aliased_type.label_group_id,
                        temp_t.user_id == current_user.user_id,
                    )
                )
            )
        )
    return q
