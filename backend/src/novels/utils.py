from ..labels.schemas import Label
from .schemas import TextOp


def apply_text_op(text : str, op : TextOp, labels : list[Label]) -> tuple[str, list[Label]]:
    """
    Apply a text operation (insertion or deletion) to the given text content, and update the positions of any labels accordingly. Throw an exception if the text operation is invalid (e.g. out of bounds).
    """
    if op.op == "delete":
        if op.start < 0 or op.start >= len(text):
            raise ValueError("Invalid text operation: start position is out of bounds")
        if op.start + len(op.text) > len(text):
            raise ValueError("Invalid text operation: text to delete is out of bounds")
        if text[op.start:op.start+len(op.text)] != op.text:
            raise ValueError("Invalid text operation: text to delete does not match existing text")
        if len(op.text) == 0:
            return text, labels
        start = op.start
        end = op.start + len(op.text)
        labels_to_move = [label for label in labels if label.label_start >= end]
        labels_to_preserve = [label for label in labels if label.label_end <= start]
        for label in labels_to_move:
            label.label_start -= len(op.text)
            label.label_end -= len(op.text)
        new_text = text[:start] + text[end:]
        return new_text, labels_to_preserve + labels_to_move
    else:
        if op.start < 0 or op.start > len(text):
            raise ValueError("Invalid text operation: start position is out of bounds")
        if len(op.text) == 0:
            return text, labels
        labels_to_move = [label for label in labels if label.label_start >= op.start]
        labels_to_preserve = [label for label in labels if label.label_end <= op.start]
        for label in labels_to_move:
            label.label_start += len(op.text)
            label.label_end += len(op.text)
        new_text = text[:op.start] + op.text + text[op.start:]
        return new_text, labels_to_preserve + labels_to_move

def apply_text_ops(text : str, ops : list[TextOp], labels : list[Label]) -> tuple[str, list[Label]]:
    """
    Apply a list of text operations to the given text content, and update the positions of any labels accordingly. The text operations are applied in order; each operation sees the text and labels as modified by all previous operations. Throw an exception if any text operation is invalid.
    """
    for op in ops:
        text, labels = apply_text_op(text, op, labels)
    return text, labels
