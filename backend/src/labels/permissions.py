"""
Module for putting permission restrictions on database queries.

Todo:
Fix inconsistencies between whether to use src.novels.permissions in conjunction or do all permission checking in this module.
"""

from sqlalchemy import Delete, Select, Update, and_, exists, or_, select

from ..auth.constants import UserType
from ..auth.models import User
from ..novels import models as novel_models
from ..novels.constants import Role, Visibility
from .constants import LabelRole
from .models import Label, LabelContributor, LabelData, LabelGroup


def label_group_mod_access_select[T : Select](q : T, current_user : User) -> T:
    """
    Takes a select statement for label groups and returns a select statement that restricts permissions on q.
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
                        LabelContributor.label_group_id == LabelGroup.label_group_id,
                        LabelContributor.user_id == current_user.user_id
                    )
                )
            )
        )
    return q

def label_group_mod_access_insert[T : Select](q : T, current_user : User, novel_id : int) -> T:
    """
    Takes a select statement used for an insert statement for label groups and returns a select statement that restricts permissions on q.
    """
    if current_user.user_type != UserType.ADMIN:
        return q.where(
            exists(
                select(
                    1
                ).select_from(
                    novel_models.Contributor
                ).where(
                    novel_models.Contributor.novel_id == novel_id
                ).where(
                    novel_models.Contributor.user_id == current_user.user_id
                ).where(
                    novel_models.Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return q

def label_group_mod_access_update[T : Update](q : T, current_user : User) -> T:
    """
    Takes an update statement for label groups and returns an update statement that restricts permissions on q.
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
                        LabelContributor.label_group_id == LabelGroup.label_group_id,
                        LabelContributor.user_id == current_user.user_id,
                        LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                    )
                )
            )
        )
    return q

def label_data_mod_access_select[T : Select](q : T, current_user : User) -> T:
    """
    Takes a select statement for label datas and returns a select statement that restricts permissions on q.
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

def label_data_mod_access_insert[T : Select](q : T, current_user : User, label_group_id : int) -> T:
    """
    Takes a select statement used for an insert from select statement for label datas and returns a select statement for a label data that restricts permissions on q.
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
                        novel_models.Contributor,
                        novel_models.Contributor.novel_id == novel_models.Novel.novel_id
                    ).where(
                        novel_models.Contributor.user_id == current_user.user_id
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

def label_mod_access_insert[T : Select](q : T, current_user : User, label_data_id : int) -> T:
    """
    Takes a select statement used for an insert from select statement for labels and returns a select statement for a label that restricts permissions on q.
    """
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
        ).where(
            or_(
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
                        novel_models.Novel, LabelGroup.novel_id == novel_models.Novel.novel_id
                    ).join(
                        novel_models.Contributor,
                        novel_models.Contributor.novel_id == novel_models.Novel.novel_id
                    ).where(
                        novel_models.Contributor.user_id == current_user.user_id
                    )
                ),
                select(
                    novel_models.Novel.novel_visibility
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == label_data_id
                ).join(
                    LabelGroup,
                    LabelGroup.label_group_id == LabelData.label_group_id
                ).join(
                    novel_models.Novel,
                    novel_models.Novel.novel_id == LabelGroup.novel_id
                ).scalar_subquery() >= Visibility.UNLISTED
            )
        )
    return q

def label_mod_access_update[T : Update](q : T, current_user : User) -> T:
    """
    Takes an update statement for labels and returns an update statement that restricts permissions on q.
    """
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
        ).where(
            or_(
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
                        novel_models.Novel, LabelGroup.novel_id == novel_models.Novel.novel_id
                    ).join(
                        novel_models.Contributor,
                        novel_models.Contributor.novel_id == novel_models.Novel.novel_id
                    ).where(
                        novel_models.Contributor.user_id == current_user.user_id
                    )
                ),
                select(
                    novel_models.Novel.novel_visibility
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == Label.label_data_id
                ).join(
                    LabelGroup,
                    LabelGroup.label_group_id == LabelData.label_group_id
                ).join(
                    novel_models.Novel,
                    novel_models.Novel.novel_id == LabelGroup.novel_id
                ).scalar_subquery() >= Visibility.UNLISTED
            )
        )
    return q

def label_mod_access_delete[T : Delete](q : T, current_user : User) -> T:
    """
    Takes a delete statement for labels and returns a delete statement that restricts permissions on q.
    """
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
        ).where(
            or_(
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
                        novel_models.Novel, LabelGroup.novel_id == novel_models.Novel.novel_id
                    ).join(
                        novel_models.Contributor,
                        novel_models.Contributor.novel_id == novel_models.Novel.novel_id
                    ).where(
                        novel_models.Contributor.user_id == current_user.user_id
                    )
                ),
                select(
                    novel_models.Novel.novel_visibility
                ).select_from(
                    LabelData
                ).where(
                    LabelData.label_data_id == Label.label_data_id
                ).join(
                    LabelGroup,
                    LabelGroup.label_group_id == LabelData.label_group_id
                ).join(
                    novel_models.Novel,
                    novel_models.Novel.novel_id == LabelGroup.novel_id
                ).scalar_subquery() >= Visibility.UNLISTED
            )
        )
    return q
