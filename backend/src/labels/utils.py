"""
Utilities for label services.
"""

import uuid
from typing import Any

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import and_, delete, insert, literal, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from ..auth.models import User
from . import models, schemas
from .exceptions import (
    LabelDataNotFoundException,
    LabelExclusionViolationInvalidOperationException,
    LabelInvalidOperationException,
    LabelNotExistsInvalidOperationException,
    LabelOutOfBoundsInvalidOperationException,
    LabelWordMismatchInvalidOperationException,
)
from .permissions import label_mod_access_delete, label_mod_access_insert, label_mod_access_update


def _apply_add(db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.AddLabelOp) -> None:
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
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
        LabelDataNotFoundException: If LabelData with label_data_id does not exist, or insufficient permissions to access with the current_user.
        LabelExclusionViolationInvalidOperationException: If an exclusion constraint is violated.
    """
    if op.end_pos > len(text):
        raise LabelOutOfBoundsInvalidOperationException
    if text[op.start_pos : op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    vals = select(
        literal(op.entity_group),
        literal(op.score),
        literal(op.word),
        literal(op.start_pos),
        literal(op.end_pos),
        literal(op.dirty),
        literal(label_data_id),
    )
    cols = [
        "label_entity_group",
        "label_score",
        "label_word",
        "label_start",
        "label_end",
        "label_dirty",
        "label_data_id",
    ]
    vals = label_mod_access_insert(vals, current_user, label_data_id)
    stmt = insert(models.Label).from_select(cols, vals).returning(models.Label)
    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise LabelDataNotFoundException from e
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.EXCLUSION_VIOLATION:
                raise LabelExclusionViolationInvalidOperationException from e
        raise
    except Exception:
        db.rollback()
        raise


def _apply_update(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.UpdateLabelOp
) -> None:
    """
    Applies a label update operation to database. Does not commit. Secure operation.

    Args:
        db: Database to update.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Update operation data.

    Raises:
        LabelOutOfBoundsInvalidOperationException: If the range [op.start_pos:op.end_pos] overflows the range of text.
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word, or similarly if the updated ranges do not match the updated word.
        LabelDataNotFoundException: If LabelData with label_data_id does not exist, or insufficient permissions to access with the current_user.
        LabelExclusionViolationInvalidOperationException: If an exclusion constraint is violated.
        LabelInvalidOperationException: If new word is set but neither new_start_pos nor new_end_pos are set.
    """
    if op.end_pos > len(text):
        raise LabelOutOfBoundsInvalidOperationException
    if text[op.start_pos : op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    if op.new_end_pos is not None and op.new_end_pos > len(text):
        raise LabelOutOfBoundsInvalidOperationException
    new_start_pos = op.new_start_pos if op.new_start_pos is not None else op.start_pos
    new_end_pos = op.new_end_pos if op.new_end_pos is not None else op.end_pos
    if op.new_start_pos is not None or op.new_end_pos is not None:
        if op.new_word is None:
            raise LabelWordMismatchInvalidOperationException
        if text[new_start_pos:new_end_pos] != op.new_word:
            raise LabelWordMismatchInvalidOperationException
    elif op.new_start_pos is None and op.new_end_pos is None:
        if op.new_word is not None:
            raise LabelInvalidOperationException("New word should not be set.")
    vals: dict[str, Any] = {}
    if op.new_start_pos is not None:
        vals["label_start"] = op.new_start_pos
    if op.new_end_pos is not None:
        vals["label_end"] = op.new_end_pos
    if op.new_start_pos is not None or op.new_end_pos is not None:
        vals["label_word"] = op.new_word
    if op.dirty is not None:
        vals["label_dirty"] = op.dirty
    if op.entity_group is not None:
        vals["label_entity_group"] = op.entity_group
    if op.score is not None:
        vals["label_score"] = op.score

    stmt = (
        update(models.Label)
        .values(vals)
        .where(
            and_(
                models.Label.label_start == op.start_pos,
                models.Label.label_end == op.end_pos,
                models.Label.label_data_id == label_data_id,
                models.Label.label_word == op.word,
            )
        )
        .returning(models.Label)
    )
    stmt = label_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise LabelDataNotFoundException from e
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.EXCLUSION_VIOLATION:
                raise LabelExclusionViolationInvalidOperationException from e
        raise
    except Exception:
        db.rollback()
        raise


def _apply_delete(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.DeleteLabelOp
) -> None:
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
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
        LabelOutOfBoundsInvalidOperationException: If the range [op.start_pos:op.end_pos] overflows the range of text.
    """
    if op.end_pos > len(text):
        raise LabelOutOfBoundsInvalidOperationException
    if text[op.start_pos : op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    stmt = delete(models.Label).where(
        and_(
            models.Label.label_start == op.start_pos,
            models.Label.label_end == op.end_pos,
            models.Label.label_data_id == label_data_id,
            models.Label.label_word == op.word,
        )
    )
    stmt = label_mod_access_delete(stmt, current_user)
    stmt = stmt.returning(models.Label)

    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise LabelNotExistsInvalidOperationException from e
    except Exception:
        db.rollback()
        raise


def apply_operation(
    db: Session, current_user: User, label_data_id: uuid.UUID, text: str, op: schemas.LabelOpBase
) -> None:
    """
    Applies a single label operation.

    Args:
        db: Database to apply operation on.
        text: Chapter text.
        entities: List of entities being kept track of in memory. Entries of the form
            (start_pos, end_pos) : models.Label
        op: Operation data.

    Raises:
        LabelOutOfBoundsInvalidOperationException: If the operation refers to positions outside the text bounds.
        LabelWordMismatchInvalidOperationException: If the word provided in the operation does not match the text at the specified positions.
        LabelDataNotFoundException: If the LabelData does not exist or the user lacks permissions.
        LabelExclusionViolationInvalidOperationException: If an add/update operation creates an overlapping label (exclusion constraint violation).
        LabelNotExistsInvalidOperationException: If a delete operation targets a label that does not exist.
        LabelInvalidOperationException: If an update operation is malformed (e.g. setting a new word without moving the label).

    Note:
        This function acts as a wrapper for calling `_apply_(add, update, delete)`. See documentation for these functions for when the corresponding types of operations get passed into op.
    """
    if isinstance(op, schemas.AddLabelOp):
        _apply_add(db, current_user, label_data_id, text, op)
    elif isinstance(op, schemas.UpdateLabelOp):
        _apply_update(db, current_user, label_data_id, text, op)
    elif isinstance(op, schemas.DeleteLabelOp):
        _apply_delete(db, current_user, label_data_id, text, op)
    else:
        raise LabelInvalidOperationException("Unknown operation type.")
