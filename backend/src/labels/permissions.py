"""
Module for putting permission restrictions on database queries.

Label read access follows novel read access (visibility or novel contributor);
label write access requires novel owner or editor access (or admin).
"""

import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, exists, select
from sqlalchemy.orm import aliased

from src.auth.models import User
from src.labels.models import Label, LabelData, LabelGroup
from src.novels import models as novel_models
from src.novels.permissions import chapter_content_mod_access_select, novel_mod_access_select


def label_group_mod_access_select[T: Select[*tuple[Any, ...]]](
    q: T,
    current_user: User,
    aliased_type: type[LabelGroup] = LabelGroup,
    *,
    edit_only: bool = False,
) -> T:
    """
    Takes a select statement for label groups and returns a select statement that restricts permissions on q.

    Setting ``edit_only`` requires owner/editor access to the underlying novel.
    """
    novel_alias = aliased(novel_models.Novel)

    q_exists_novel = (
        select(novel_alias.novel_id).where(novel_alias.novel_id == aliased_type.novel_id).correlate(aliased_type)
    )
    q_exists_novel = novel_mod_access_select(
        q_exists_novel,
        current_user,
        novel_alias,
        edit_only=edit_only,
    )
    return q.where(exists(q_exists_novel))


def label_group_mod_access_insert[T: Select[*tuple[Any, ...]]](q: T, current_user: User, novel_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert statement for label groups and returns a select statement that restricts permissions on q.
    """
    novel_alias = aliased(novel_models.Novel)
    q_exists_novel = select(novel_alias.novel_id).where(novel_alias.novel_id == novel_id)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user, novel_alias, edit_only=True)
    return q.where(exists(q_exists_novel))


def label_group_mod_access_update[T: Update](
    q: T, current_user: User, aliased_type: type[LabelGroup] = LabelGroup
) -> T:
    """
    Takes an update statement for label groups and returns an update statement that restricts permissions on q.
    """
    novel_alias = aliased(novel_models.Novel)

    q_exists_novel = (
        select(novel_alias.novel_id).where(novel_alias.novel_id == aliased_type.novel_id).correlate(aliased_type)
    )
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user, novel_alias, edit_only=True)
    return q.where(exists(q_exists_novel))


def label_data_mod_access_select[T: Select[*tuple[Any, ...]]](
    q: T,
    current_user: User,
    aliased_type: type[LabelData] = LabelData,
    *,
    edit_only: bool = False,
) -> T:
    """
    Takes a select statement for label datas and returns a select statement that restricts permissions on q.
    """
    cc_alias = aliased(novel_models.ChapterContent)
    lg_alias = aliased(LabelGroup)

    q_exists_chapter_content = (
        select(cc_alias.chapter_content_id)
        .where(cc_alias.chapter_content_id == aliased_type.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(
        q_exists_chapter_content,
        current_user,
        cc_alias,
        edit_only=edit_only,
    )
    q_exists_label_group = (
        select(lg_alias.label_group_id)
        .where(lg_alias.label_group_id == aliased_type.label_group_id)
        .correlate(aliased_type)
    )
    q_exists_label_group = label_group_mod_access_select(
        q_exists_label_group,
        current_user,
        lg_alias,
        edit_only=edit_only,
    )
    return q.where(exists(q_exists_chapter_content)).where(exists(q_exists_label_group))


def label_data_mod_access_update[T: Update](q: T, current_user: User, aliased_type: type[LabelData] = LabelData) -> T:
    """
    Takes an update statement for label datas and returns an update statement that restricts permissions on q.
    """
    cc_alias = aliased(novel_models.ChapterContent)
    lg_alias = aliased(LabelGroup)

    q_exists_chapter_content = (
        select(cc_alias.chapter_content_id)
        .where(cc_alias.chapter_content_id == aliased_type.chapter_content_id)
        .correlate(aliased_type)
    )
    q_exists_chapter_content = chapter_content_mod_access_select(
        q_exists_chapter_content,
        current_user,
        cc_alias,
        edit_only=True,
    )
    q_exists_label_group = (
        select(lg_alias.label_group_id)
        .where(lg_alias.label_group_id == aliased_type.label_group_id)
        .correlate(aliased_type)
    )
    q_exists_label_group = label_group_mod_access_select(
        q_exists_label_group,
        current_user,
        lg_alias,
        edit_only=True,
    )
    return q.where(exists(q_exists_chapter_content)).where(exists(q_exists_label_group))


def label_data_mod_access_insert[T: Select[*tuple[Any, ...]]](q: T, current_user: User, label_group_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for label datas and returns a select statement for a label data that restricts permissions on q.
    """
    lg_alias = aliased(LabelGroup)
    q_exists_label_group = select(lg_alias.label_group_id).where(lg_alias.label_group_id == label_group_id)
    q_exists_label_group = label_group_mod_access_select(
        q_exists_label_group,
        current_user,
        lg_alias,
        edit_only=True,
    )
    return q.where(exists(q_exists_label_group))


def label_mod_access_insert[T: Select[*tuple[Any, ...]]](q: T, current_user: User, label_data_id: uuid.UUID) -> T:
    """
    Takes a select statement used for an insert from select statement for labels and returns a select statement for a label that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    q_exists_label_data = select(ld_alias.label_data_id).where(ld_alias.label_data_id == label_data_id)
    q_exists_label_data = label_data_mod_access_select(
        q_exists_label_data,
        current_user,
        ld_alias,
        edit_only=True,
    )
    return q.where(exists(q_exists_label_data))


def label_mod_access_update[T: Update](q: T, current_user: User, aliased_type: type[Label] = Label) -> T:
    """
    Takes an update statement for labels and returns an update statement that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    q_exists_label_data = (
        select(ld_alias.label_data_id)
        .where(ld_alias.label_data_id == aliased_type.label_data_id)
        .correlate(aliased_type)
    )
    q_exists_label_data = label_data_mod_access_select(
        q_exists_label_data,
        current_user,
        ld_alias,
        edit_only=True,
    )
    return q.where(exists(q_exists_label_data))


def label_mod_access_delete[T: Delete](q: T, current_user: User, aliased_type: type[Label] = Label) -> T:
    """
    Takes a delete statement for labels and returns a delete statement that restricts permissions on q.
    """
    ld_alias = aliased(LabelData)
    q_exists_label_data = (
        select(ld_alias.label_data_id)
        .where(ld_alias.label_data_id == aliased_type.label_data_id)
        .correlate(aliased_type)
    )
    q_exists_label_data = label_data_mod_access_select(
        q_exists_label_data,
        current_user,
        ld_alias,
        edit_only=True,
    )
    return q.where(exists(q_exists_label_data))
