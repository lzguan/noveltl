"""
Utilities for label services.
"""

from sqlalchemy import literal, insert, select, update, delete, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from . import schemas
from . import models
from .permissions import *
from .models import *
from .exceptions import *

def _apply_add(db : Session, current_user : User, label_data_id : int, text : str, op : schemas.AddLabelOp) -> None:
    """
    Applies a label add operation to database. Does not commit.

    Args:
        db: Database to insert into.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Add operation data.
    
    Raises:
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
        LabelAlreadyExistsInvalidOperationException: If the entities dictionary already has a label starting/ending at op.start_pos/op.end_pos.

    Note:
        This function does not perform range checks.
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
        literal(label_data_id)
    )
    cols = [
        'label_entity_group',
        'label_score',
        'label_word',
        'label_start',
        'label_end',
        'label_dirty',
        'label_data_id'
    ]
    vals = label_mod_access_insert(vals, current_user, label_data_id)
    stmt = insert(models.Label).from_select(cols, vals).returning(models.Label)
    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise e

def _apply_update(db : Session, current_user : User, label_data_id : int, text : str, op : schemas.UpdateLabelOp) -> None:
    """
    Applies a label update operation to database. Does not commit.

    Args:
        db: Database to update.
        current_user: User performing the operation.
        label_data_id: id of label data.
        text: Chapter text.
        op: Update operation data.
    
    Raises:
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
        LabelNotExistsInvalidOperationException: If the entities dictionary does not have a label with op.start_pos, op.end_pos in it.
    
    Note:
        This function does not perform range checks.
    """
    if text[op.start_pos:op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    vals = {}
    if op.new_start_pos is not None:
        vals['label_start'] = op.new_start_pos
    if op.new_end_pos is not None:
        vals['label_end'] = op.new_end_pos
    if op.new_word is not None:
        vals['label_word'] = op.new_word
    if op.dirty is not None:
        vals['label_dirty'] = op.dirty
    if op.entity_group is not None:
        vals['label_entity_group'] = op.entity_group
    if op.score is not None:
        vals['label_score'] = op.score

    stmt = update(
        models.Label
    ).values(
        vals
    ).where(
        and_(
            models.Label.label_start == op.start_pos,
            models.Label.label_end == op.end_pos,
            models.Label.label_data_id == label_data_id,
            models.Label.label_word == op.word
        )
    ).returning(
        models.Label
    )
    stmt = label_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise e

def _apply_delete(db : Session, current_user : User, label_data_id : int, text : str, op : schemas.DeleteLabelOp) -> None:
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
    """
    if text[op.start_pos:op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    stmt = delete(models.Label).where(
        and_(
            models.Label.label_start == op.start_pos,
            models.Label.label_end == op.end_pos,
            models.Label.label_data_id == label_data_id,
            models.Label.label_word == op.word
        )
    )
    stmt = label_mod_access_delete(stmt, current_user)
    stmt = stmt.returning(
        models.Label
    )

    try:
        result = db.execute(stmt)
        result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise e
    


def apply_operation(db : Session, current_user : User, label_data_id : int, text : str, op : schemas.LabelOpBase) -> None:
    """
    Applies a single label operation.

    Args:
        db: Database to apply operation on.
        text: Chapter text.
        entities: List of entities being kept track of in memory. Entries of the form
            (start_pos, end_pos) : models.Label
        op: Operation data.
    
    Raises:
        LabelNotExistsInvalidOperationException:
        LabelWordMismatchInvalidOperationException:
        LabelAlreadyExistsInvalidOperationException:
    
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
        raise UnknownError(f"Unknown operation type: {type(op)}")
    
