import logging
import uuid
from typing import Any

from sqlalchemy import insert, literal, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from ..auth.models import User
from ..labels import models as label_models
from ..labels.constants import LabelRole
from ..labels.exceptions import LabelGroupNotFoundException
from ..labels.permissions import (
    label_data_mod_access_insert,
    label_group_mod_access_select,
)

logger = logging.getLogger(__name__)


def find_sentence_around(text: str, label_start: int, label_end: int, delimiters: str) -> tuple[str, int, int]:
    """
    Finds the sentence surrounding a labeled segment in the text. Returns in the format (sentence, label_start, label_end).
    """
    # Find sentence start (last delimiter before label_start)
    start = 0
    for delim in delimiters:
        pos = text.rfind(delim, 0, label_start)
        if pos != -1 and pos + 1 > start:
            start = pos + 1

    # Find sentence end (first delimiter after label_end)
    end = len(text)
    for delim in delimiters:
        pos = text.find(delim, label_end)
        if pos != -1 and pos + 1 < end:
            end = pos + 1

    if end - start > 500:
        logger.warning(
            "find_sentence_around returned %d chars (label: %d-%d). Possibly missing delimiter.",
            end - start,
            label_start,
            label_end,
        )

    return text[start:end].strip(), label_start - start, label_end - start


def copy_label_group(
    db: Session,
    current_user: User,
    label_group_id: uuid.UUID,
    new_label_group_name: str,
    keep_contributors: bool = True,
) -> label_models.LabelGroup:
    """
    Copies a label group with a new name. Only editors may copy label groups. The new label group will have the same novel association as the original. The label data and labels associated with the original label group will also be copied to the new label group.

    Args:
        db: SQLAlchemy session for database access.
        current_user: The user requesting the label group copy.
        label_group_id: The ID of the label group to copy.
        new_label_group_name: The name for the new label group.
        keep_contributors: Whether to keep the same contributors in the new label group. If False, the current user will be set as the only contributor with the role of 'owner'. Otherwise, all contributors from the original label group will be copied to the new label group with the same roles.

    Raises:
        LabelGroupNotFoundException: If the original label group with the given ID does not exist or the user does not have access to it.
        LabelgroupCopyException: If there is an error specific to the label group copying process (e.g., database integrity error).
    """

    # label group
    q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group_id)
    q = label_group_mod_access_select(q, current_user, only_editors=True)
    try:
        result = db.execute(q)
        original_label_group = result.scalar_one()
    except NoResultFound as e:
        raise LabelGroupNotFoundException(label_group_id) from e
    except Exception:
        db.rollback()
        raise

    stmt = (
        insert(label_models.LabelGroup)
        .values(label_group_name=new_label_group_name, novel_id=original_label_group.novel_id)
        .returning(label_models.LabelGroup)
    )
    try:
        new_label_group = db.execute(stmt).scalar_one()
    except Exception:
        db.rollback()
        raise

    # contributors
    if keep_contributors:
        cols: list[Any] = [
            label_models.LabelContributor.user_id,
            label_models.LabelContributor.label_group_id,
            label_models.LabelContributor.label_contributor_role,
        ]
        q = (
            select(
                label_models.LabelContributor.user_id,
                literal(new_label_group.label_group_id),
                label_models.LabelContributor.label_contributor_role,
            )
            .select_from(label_models.LabelContributor)
            .where(label_models.LabelContributor.label_group_id == original_label_group.label_group_id)
        )
        stmt = insert(label_models.LabelContributor).from_select(cols, q)
    else:
        stmt = insert(label_models.LabelContributor).values(
            user_id=current_user.user_id,
            label_group_id=new_label_group.label_group_id,
            label_contributor_role=LabelRole.OWNER,
        )

    try:
        db.execute(stmt)
    except Exception:
        db.rollback()
        raise

    # label datas
    cols = [label_models.LabelData.chapter_content_id, label_models.LabelData.label_group_id]
    q_label_datas = (
        select(label_models.LabelData.chapter_content_id, literal(new_label_group.label_group_id))
        .select_from(label_models.LabelData)
        .where(label_models.LabelData.label_group_id == original_label_group.label_group_id)
    )
    q_label_datas = label_data_mod_access_insert(q_label_datas, current_user, original_label_group.label_group_id)
    stmt = insert(label_models.LabelData).from_select(cols, q_label_datas).returning(label_models.LabelData)
    try:
        db.execute(stmt)
    except Exception:
        db.rollback()
        raise

    # labels
    cols = [
        label_models.Label.label_data_id,
        label_models.Label.label_entity_group,
        label_models.Label.label_word,
        label_models.Label.label_start,
        label_models.Label.label_end,
        label_models.Label.label_score,
        label_models.Label.label_dirty,
    ]
    old_ld = aliased(label_models.LabelData)
    q_labels = (
        select(
            label_models.LabelData.label_data_id,
            label_models.Label.label_entity_group,
            label_models.Label.label_word,
            label_models.Label.label_start,
            label_models.Label.label_end,
            label_models.Label.label_score,
            label_models.Label.label_dirty,
        )
        .select_from(label_models.Label)
        .join(old_ld, label_models.Label.label_data_id == old_ld.label_data_id)
        .where(old_ld.label_group_id == original_label_group.label_group_id)
        .join(label_models.LabelData, label_models.LabelData.chapter_content_id == old_ld.chapter_content_id)
        .where(label_models.LabelData.label_group_id == new_label_group.label_group_id)
    )
    # add permissions? stc
    stmt = insert(label_models.Label).from_select(cols, q_labels)
    try:
        db.execute(stmt)
    except Exception:
        db.rollback()
        raise

    db.commit()
    db.refresh(new_label_group)
    return new_label_group
