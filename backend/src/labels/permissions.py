"""
Module for putting permission restrictions on database queries.

If a function from this module is called, the permissions on the novel are automatically restricted as well. As of right now, the permissions on the novel/revision are checked only by whether the current user can view it.
"""
import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, and_, exists, literal, or_, select

from ..auth.constants import UserType
from ..auth.models import User
from ..novels import models as novel_models
from ..novels.constants import Visibility
from ..novels.permissions import chapter_content_mod_access_select, novel_mod_access_select
from .constants import LabelRole
from .models import Label, LabelContributor, LabelData, LabelGroup


def label_group_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User, only_editors : bool = False) -> T:
    """
    Takes a select statement for label groups and returns a select statement that restricts permissions on q.
    """
    q_exists_novel = select(novel_models.Novel.novel_id).where(novel_models.Novel.novel_id == LabelGroup.novel_id).correlate(LabelGroup)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user)
    q = q.where(exists(q_exists_novel))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelContributor
                ).where(
                    and_(
                        LabelContributor.label_group_id == LabelGroup.label_group_id,
                        LabelContributor.user_id == current_user.user_id,
                        or_(
                            literal(only_editors is False),
                            LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                        )
                    )
                )
            )
        )
    return q

def label_group_mod_access_insert[T : Select[tuple[Any, ...]]](q : T, current_user : User, novel_id : uuid.UUID) -> T:
    """
    Takes a select statement used for an insert statement for label groups and returns a select statement that restricts permissions on q.
    """
    q_exists_novel = select(novel_models.Novel.novel_id).where(novel_models.Novel.novel_id == novel_id)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user)
    q = q.where(exists(q_exists_novel))
    return q

def label_group_mod_access_update[T : Update](q : T, current_user : User) -> T:
    """
    Takes an update statement for label groups and returns an update statement that restricts permissions on q.
    """
    q_exists_novel = select(novel_models.Novel.novel_id).where(novel_models.Novel.novel_id == LabelGroup.novel_id).correlate(LabelGroup)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user)
    q = q.where(exists(q_exists_novel))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelContributor
                ).where(
                    and_(
                        LabelContributor.label_group_id == LabelGroup.label_group_id,
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                    )
                )
            )
        )
    return q

def label_data_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User) -> T:
    """
    Takes a select statement for label datas and returns a select statement that restricts permissions on q.
    """
    q_exists_chapter_content = select(novel_models.ChapterContent.chapter_content_id).where(novel_models.ChapterContent.chapter_content_id == LabelData.chapter_content_id).correlate(LabelData)
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelContributor
                ).where(
                    and_(
                        LabelContributor.label_group_id == LabelData.label_group_id,
                        LabelContributor.user_id == current_user.user_id
                    )
                )
            )
        )
    return q

def label_data_mod_access_update[T : Update](q : T, current_user : User) -> T:
    """
    Takes an update statement for label datas and returns an update statement that restricts permissions on q.
    """
    q_exists_chapter_content = select(novel_models.ChapterContent.chapter_content_id).where(novel_models.ChapterContent.chapter_content_id == LabelData.chapter_content_id).correlate(LabelData)
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelContributor
                ).where(
                    and_(
                        LabelContributor.label_group_id == LabelData.label_group_id,
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                    )
                )
            )
        )
    return q

def label_data_mod_access_insert[T : Select[tuple[Any, ...]]](q : T, current_user : User, label_group_id : uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for label datas and returns a select statement for a label data that restricts permissions on q.

    As of right now, this function grants permissions to insert label datas if the user has edit permissions on the label group and has permission to view the public chapters of the corresponding novel. This may create more label datas for the user than intended, but other permission filters restrict view access to the label datas inserted for revisions the user doesn't have access to, so this is not a security issue. This is done this way because it's difficult to restrict permissions on insert from select statements without introducing extra parameters, which hampers flexibility. STC.
    """
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelContributor
                ).where(
                    and_(
                        LabelContributor.label_group_id == label_group_id,
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                    )
                )
            )
        ).where(
            or_(
                exists(
                    select(
                        1
                    ).select_from(
                        LabelGroup
                    ).where(
                        LabelGroup.label_group_id == label_group_id
                    ).join(
                        novel_models.Novel, LabelGroup.novel_id == novel_models.Novel.novel_id
                    ).join(
                        novel_models.NovelContributor,
                        novel_models.NovelContributor.novel_id == novel_models.Novel.novel_id
                    ).where(
                        novel_models.NovelContributor.user_id == current_user.user_id
                    )
                ),
                select(
                    novel_models.Novel.novel_visibility
                ).select_from(
                    LabelGroup
                ).where(
                    LabelGroup.label_group_id == label_group_id
                ).join(
                    novel_models.Novel,
                    novel_models.Novel.novel_id == LabelGroup.novel_id
                ).scalar_subquery() >= Visibility.UNLISTED
            )
        )
    return q

def label_mod_access_insert[T : Select[tuple[Any, ...]]](q : T, current_user : User, label_data_id : uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for labels and returns a select statement for a label that restricts permissions on q.
    """
    q_exists_chapter_content = select(
        1
    ).select_from(
        LabelData
    ).where(
        LabelData.label_data_id == label_data_id
    ).join(
        novel_models.ChapterContent,
        novel_models.ChapterContent.chapter_content_id == LabelData.chapter_content_id
    )
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == label_data_id
                ).join(
                    LabelGroup, LabelData.label_group_id == LabelGroup.label_group_id
                ).join(
                    LabelContributor, LabelGroup.label_group_id == LabelContributor.label_group_id
                ).where(
                    and_(
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER])
                    )
                )
            )
        )
    return q

def label_mod_access_update[T : Update](q : T, current_user : User) -> T:
    """
    Takes an update statement for labels and returns an update statement that restricts permissions on q.
    """
    q_exists_chapter_content = select(
        1
    ).select_from(
        LabelData
    ).where(
        LabelData.label_data_id == Label.label_data_id  # Correlates to outer Label
    ).join(
        novel_models.ChapterContent,
        LabelData.chapter_content_id == novel_models.ChapterContent.chapter_content_id
    ).correlate(Label)
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == Label.label_data_id
                ).join(
                    LabelGroup, LabelData.label_group_id == LabelGroup.label_group_id
                ).join(
                    LabelContributor, LabelGroup.label_group_id == LabelContributor.label_group_id
                ).where(
                    and_(
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER])
                    )
                )
            )
        )
    return q

def label_mod_access_delete[T : Delete](q : T, current_user : User) -> T:
    """
    Takes a delete statement for labels and returns a delete statement that restricts permissions on q.
    """
    q_exists_chapter_content = select(
        1
    ).select_from(
        LabelData
    ).where(
        LabelData.label_data_id == Label.label_data_id  # Correlates to outer Label
    ).join(
        novel_models.ChapterContent,
        LabelData.chapter_content_id == novel_models.ChapterContent.chapter_content_id
    ).correlate(Label)
    q_exists_chapter_content = chapter_content_mod_access_select(q_exists_chapter_content, current_user)
    q = q.where(exists(q_exists_chapter_content))
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == Label.label_data_id
                ).join(
                    LabelGroup, LabelData.label_group_id == LabelGroup.label_group_id
                ).join(
                    LabelContributor, LabelGroup.label_group_id == LabelContributor.label_group_id
                ).where(
                    and_(
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.EDITOR, LabelRole.OWNER])
                    )
                )
            )
        )
    return q
