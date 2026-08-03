"""
Utilities for label services.
"""

import uuid

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import and_, delete, insert, literal, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from src.auth.models import User
from src.labels import models, schemas
from src.labels.constants import MAX_LABEL_WORD_LEN
from src.labels.exceptions import (
    LabelConcurrentModificationException,
    LabelDataNotFoundException,
    LabelExclusionViolationInvalidOperationException,
    LabelInvalidOperationException,
    LabelNotExistsInvalidOperationException,
    LabelOutOfBoundsInvalidOperationException,
)
from src.labels.permissions import label_mod_access_delete, label_mod_access_insert, label_mod_access_update
from src.labels.schemas import OpResult


def _apply_add(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.AddLabelOp
) -> OpResult:
    """
    Applies a label add operation to database. Does not commit. Secure operation.

    Args:
        db: Database to insert into.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Add operation data.

    Raises:
        LabelOutOfBoundsInvalidOperationException: If the range [op.start_pos:op.end_pos] overflows the range of text.
        LabelDataNotFoundException: If LabelData with label_data_id does not exist, or insufficient permissions to access with the current_user.
        LabelExclusionViolationInvalidOperationException: If an exclusion constraint is violated.
    """
    if op.end_pos > len(text):
        raise LabelOutOfBoundsInvalidOperationException
    vals = select(
        literal(op.entity_group),
        literal(op.score),
        literal(op.start_pos),
        literal(op.end_pos),
        literal(op.dirty),
        literal(label_data_id),
        literal(text[op.start_pos : op.end_pos]),
    )
    cols = [
        "label_entity_group",
        "label_score",
        "label_start",
        "label_end",
        "label_dirty",
        "label_data_id",
        "label_word",
    ]
    vals = label_mod_access_insert(vals, current_user, label_data_id)
    stmt = insert(models.Label).from_select(cols, vals).returning(models.Label)
    try:
        result = db.execute(stmt)
        return result.scalar_one().label_id
    except NoResultFound as e:
        raise LabelDataNotFoundException from e
    except IntegrityError as e:
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.EXCLUSION_VIOLATION:
                raise LabelExclusionViolationInvalidOperationException from e
        raise
    except Exception:
        raise


def _apply_update(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.UpdateLabelOp
) -> OpResult:
    """
    Applies a label update operation to database. Does not commit. Secure operation.

    Args:
        db: Database to update.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Update operation data.

    Raises:
        LabelNotExistsInvalidOperationException: If the target label does not exist or cannot be edited by the user.
        LabelOutOfBoundsInvalidOperationException: If the resulting range extends beyond the chapter text.
        LabelInvalidOperationException: If the resulting range is empty, reversed, or too long.
        LabelExclusionViolationInvalidOperationException: If an exclusion constraint is violated.
        LabelConcurrentModificationException: If the label changes between the read and update.
    """
    try:
        old_label = db.execute(
            label_mod_access_insert(
                select(models.Label).where(
                    models.Label.label_id == op.label_id,
                    models.Label.label_data_id == label_data_id,
                ),
                current_user,
                label_data_id,
            )  # kinda scuffed but ok
        ).scalar_one()
    except NoResultFound as e:
        raise LabelNotExistsInvalidOperationException from e
    version = old_label.version
    new_label = {
        "label_entity_group": op.entity_group if op.entity_group is not None else old_label.label_entity_group,
        "label_score": op.score if op.score is not None else old_label.label_score,
        "label_start": op.start_pos if op.start_pos is not None else old_label.label_start,
        "label_end": op.end_pos if op.end_pos is not None else old_label.label_end,
        "label_dirty": op.dirty if op.dirty is not None else old_label.label_dirty,
        "version": version + 1,  # increment version for optimistic locking
    }
    new_label["label_word"] = text[new_label["label_start"] : new_label["label_end"]]
    if new_label["label_start"] >= new_label["label_end"]:
        raise LabelInvalidOperationException("Start pos must be less than end pos")
    if new_label["label_end"] > len(text):
        raise LabelOutOfBoundsInvalidOperationException("Label end position is out of bounds")
    if new_label["label_end"] - new_label["label_start"] > MAX_LABEL_WORD_LEN:
        raise LabelInvalidOperationException(f"Label length must be less than or equal to {MAX_LABEL_WORD_LEN}")
    stmt = (
        update(models.Label)
        .values(new_label)
        .where(
            and_(
                models.Label.label_id == op.label_id,
                models.Label.label_data_id == label_data_id,
                models.Label.version == version,  # optimistic locking check
            )
        )
        .returning(models.Label)
    )
    stmt = label_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        return result.scalar_one().label_id
    except NoResultFound as e:
        raise LabelConcurrentModificationException from e
    except IntegrityError as e:
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.EXCLUSION_VIOLATION:
                raise LabelExclusionViolationInvalidOperationException from e
        raise
    except Exception:
        raise


def _apply_delete(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.DeleteLabelOp
) -> OpResult:
    """
    Applies a label delete operation. Does not commit.

    Args:
        db: Database to delete from.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Delete operation data.

    Raises:
        LabelNotExistsInvalidOperationException: If the label to delete does not exist in database.
    """
    stmt = delete(models.Label).where(
        and_(
            models.Label.label_id == op.label_id,
            models.Label.label_data_id == label_data_id,
        )
    )
    stmt = label_mod_access_delete(stmt, current_user)
    stmt = stmt.returning(models.Label)

    try:
        result = db.execute(stmt)
        return result.scalar_one().label_id
    except NoResultFound as e:
        raise LabelNotExistsInvalidOperationException from e
    except Exception:
        raise


def apply_operation(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.LabelOp
) -> OpResult:
    """
    Applies a single label operation.

    Args:
        db: Database to apply operation on.
        current_user: User performing the operation.
        label_data_id: ID of the label data being modified.
        text: Chapter text.
        op: Operation data.

    Raises:
        LabelOutOfBoundsInvalidOperationException: If the operation refers to positions outside the text bounds.
        LabelDataNotFoundException: If the LabelData does not exist or the user lacks permissions.
        LabelExclusionViolationInvalidOperationException: If an add/update operation creates an overlapping label (exclusion constraint violation).
        LabelNotExistsInvalidOperationException: If a delete operation targets a label that does not exist.
        LabelInvalidOperationException: If an operation contains an invalid range.
        LabelConcurrentModificationException: If an update loses an optimistic-lock race.

    Note:
        This function acts as a wrapper for calling `_apply_(add, update, delete)`. See documentation for these functions for when the corresponding types of operations get passed into op.
    """
    if isinstance(op, schemas.AddLabelOp):
        return _apply_add(db, current_user, label_data_id, text, op)
    elif isinstance(op, schemas.UpdateLabelOp):
        return _apply_update(db, current_user, label_data_id, text, op)
    elif isinstance(op, schemas.DeleteLabelOp):
        return _apply_delete(db, current_user, label_data_id, text, op)
    else:
        raise LabelInvalidOperationException("Unknown operation type.")
