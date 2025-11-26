"""
Utilities for label services.
"""

from typing import Dict, Tuple
from . import schemas
from . import models
from sqlalchemy.orm import Session
from .models import *
from .exceptions import *

def _apply_add(db : Session, label_data_id : int, text : str, entities : Dict[Tuple[int, int], models.Label], op : schemas.AddLabelOp) -> None:
    """
    Applies a label add operation to database. Does not commit.

    Args:
        db: Database to insert into.
        label_data_id: id of label data.
        text: Chapter text.
        entities: List of entities being kept track of in memory. Entries of the form
            (start_pos, end_pos) : models.Label
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
    if (op.start_pos, op.end_pos) in entities:
        raise LabelAlreadyExistsInvalidOperationException
    label = models.Label(
            label_entity_group=op.entity_group,
            label_score=op.score,
            label_word=op.word,
            label_start=op.start_pos,
            label_end=op.end_pos,
            label_dirty=op.dirty,
            label_data_id=label_data_id
        )
    entities[(op.start_pos, op.end_pos)] = label
    db.add(label)

def _apply_update(text : str, entities : Dict[Tuple[int, int], models.Label], op : schemas.UpdateLabelOp) -> None:
    """
    Applies a label update operation to database. Does not commit.

    Args:
        text: Chapter text.
        entities: List of entities being kept track of in memory. Entries of the form
            (start_pos, end_pos) : models.Label
        op: Update operation data.
    
    Raises:
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
        LabelNotExistsInvalidOperationException: If the entities dictionary does not have a label with op.start_pos, op.end_pos in it.
    
    Note:
        This function does not perform range checks.
    """
    if (op.start_pos, op.end_pos) not in entities:
        raise LabelNotExistsInvalidOperationException
    if text[op.start_pos:op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    
    label = entities[(op.start_pos, op.end_pos)]
    range_change = False
    cur_start = op.start_pos
    cur_end = op.end_pos
    if op.new_start_pos is not None and op.new_start_pos != op.start_pos:
        range_change = True
        cur_start = op.new_start_pos
    if op.new_end_pos is not None and op.new_end_pos != op.end_pos:
        range_change = True
        cur_end = op.new_end_pos
    if range_change:
        if cur_end > len(text):
            raise LabelOutOfBoundsInvalidOperationException
        if op.new_word is None or text[cur_start:cur_end] != op.new_word:
            raise LabelWordMismatchInvalidOperationException
        if (cur_start, cur_end) in entities:
            raise LabelAlreadyExistsInvalidOperationException
        del entities[(op.start_pos, op.end_pos)]
        label.label_word = op.new_word
        label.label_start = cur_start
        label.label_end = cur_end
        entities[(cur_start, cur_end)] = label
    if op.dirty is not None:
        label.label_dirty = op.dirty
    if op.entity_group is not None:
        label.label_entity_group = op.entity_group
    if op.score is not None:
        label.label_score = op.score

def _apply_delete(db : Session, text : str, entities : Dict[Tuple[int, int], models.Label], op : schemas.DeleteLabelOp) -> None:
    """
    Applies a label delete operation. Does not commit.

    Args:
        db: Database to delete from.
        text: Chapter text.
        entities: List of entities being kept track of in memory. Entries of the form
            (start_pos, end_pos) : models.Label
        op: Update operation data.
    
    Raises:
        LabelNotExistsInvalidOperationException: If the label to delete does not exist in database.
        LabelWordMismatchInvalidOperationException: If text[op.start_pos:op.end_pos] does not match op.word.
    """
    if not (op.start_pos, op.end_pos) in entities:
        raise LabelNotExistsInvalidOperationException
    if text[op.start_pos:op.end_pos] != op.word:
        raise LabelWordMismatchInvalidOperationException
    label = entities[(op.start_pos, op.end_pos)]
    db.delete(label)
    del entities[(op.start_pos, op.end_pos)]

def apply_operation(db : Session, label_data_id : int, text : str, entities : Dict[Tuple[int, int], models.Label], op : schemas.LabelOpBase) -> None:
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
        _apply_add(db, label_data_id, text, entities, op)
    elif isinstance(op, schemas.UpdateLabelOp):
        _apply_update(text, entities, op)
    elif isinstance(op, schemas.DeleteLabelOp):
        _apply_delete(db, text, entities, op)
    else:
        raise UnknownError(f"Unknown operation type: {type(op)}")