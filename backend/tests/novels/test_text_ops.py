"""
Unit tests for apply_text_op and apply_text_ops in novels/utils.py.

These are pure function tests — no database or fixtures needed.
"""

import uuid

import pytest

from src.labels.schemas import Label
from src.novels.schemas import TextOp
from src.novels.utils import apply_text_op, apply_text_ops


def _label(word: str, start: int, end: int, score: float = 1.0) -> Label:
    return Label(
        label_entity_group="MISC",
        label_score=score,
        label_word=word,
        label_start=start,
        label_end=end,
        label_dirty=False,
        label_data_id=uuid.uuid4(),
    )


# -------------------------------------------------------
# apply_text_op — delete
# -------------------------------------------------------


class TestDeleteOp:
    def test_delete_middle_shifts_labels(self):
        # "Hello world. Test." with labels on "Hello" [0,5) and "Test" [13,17)
        text = "Hello world. Test."
        labels = [_label("Hello", 0, 5), _label("Test", 13, 17)]
        op = TextOp(op="delete", start=5, text=" world")  # delete " world"

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello. Test."
        assert len(new_labels) == 2
        hello = next(lb for lb in new_labels if lb.label_word == "Hello")
        test = next(lb for lb in new_labels if lb.label_word == "Test")
        assert hello.label_start == 0
        assert hello.label_end == 5
        assert test.label_start == 7  # 13 - 6
        assert test.label_end == 11  # 17 - 6

    def test_delete_at_start(self):
        text = "Hello world."
        labels = [_label("world", 6, 11)]
        op = TextOp(op="delete", start=0, text="Hello ")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "world."
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0
        assert new_labels[0].label_end == 5

    def test_delete_at_end(self):
        text = "Hello world."
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="delete", start=5, text=" world.")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello"
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0
        assert new_labels[0].label_end == 5

    def test_delete_overlapping_label_removes_it(self):
        text = "Hello world. Test."
        labels = [_label("Hello", 0, 5), _label("world", 6, 11), _label("Test", 13, 17)]
        op = TextOp(op="delete", start=4, text="o world")  # overlaps "Hello" and "world"

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hell. Test."
        # "Hello" ends at 5, which is > start=4 and starts at 0, which is < end=11 → overlapping, removed
        # "world" starts at 6, ends at 11 → fully inside deletion, removed
        # "Test" starts at 13 → shifted to 13-7=6
        assert len(new_labels) == 1
        assert new_labels[0].label_word == "Test"
        assert new_labels[0].label_start == 6
        assert new_labels[0].label_end == 10

    def test_delete_empty_string_is_noop(self):
        text = "Hello world."
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="delete", start=0, text="")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == text
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0

    def test_delete_wrong_text_raises(self):
        text = "Hello world."
        op = TextOp(op="delete", start=0, text="Goodbye")

        with pytest.raises(ValueError, match="does not match"):
            apply_text_op(text, op, [])

    def test_delete_out_of_bounds_raises(self):
        text = "Hello"
        op = TextOp(op="delete", start=10, text="x")

        with pytest.raises(ValueError, match="out of bounds"):
            apply_text_op(text, op, [])

    def test_delete_extends_past_end_raises(self):
        text = "Hello"
        op = TextOp(op="delete", start=3, text="loXX")

        with pytest.raises(ValueError, match="out of bounds"):
            apply_text_op(text, op, [])

    def test_delete_negative_start_raises(self):
        text = "Hello"
        op = TextOp(op="delete", start=-1, text="H")

        with pytest.raises(ValueError, match="out of bounds"):
            apply_text_op(text, op, [])

    def test_delete_label_ending_at_boundary_preserved(self):
        # Label ends exactly at deletion start → preserved
        text = "Hello world."
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="delete", start=5, text=" ")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Helloworld."
        assert len(new_labels) == 1
        assert new_labels[0].label_word == "Hello"
        assert new_labels[0].label_start == 0
        assert new_labels[0].label_end == 5

    def test_delete_label_starting_at_deletion_end_shifts(self):
        # Label starts exactly at deletion end → shifted
        text = "Hello world."
        labels = [_label("world", 6, 11)]
        op = TextOp(op="delete", start=5, text=" ")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Helloworld."
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 5
        assert new_labels[0].label_end == 10


# -------------------------------------------------------
# apply_text_op — insert
# -------------------------------------------------------


class TestInsertOp:
    def test_insert_middle_shifts_labels(self):
        text = "Hello world."
        labels = [_label("Hello", 0, 5), _label("world", 6, 11)]
        op = TextOp(op="insert", start=5, text=" dear")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello dear world."
        assert len(new_labels) == 2
        hello = next(lb for lb in new_labels if lb.label_word == "Hello")
        world = next(lb for lb in new_labels if lb.label_word == "world")
        assert hello.label_start == 0
        assert hello.label_end == 5
        assert world.label_start == 11  # 6 + 5
        assert world.label_end == 16  # 11 + 5

    def test_insert_at_start(self):
        text = "Hello world."
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="insert", start=0, text="Dear ")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Dear Hello world."
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 5
        assert new_labels[0].label_end == 10

    def test_insert_at_end(self):
        text = "Hello"
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="insert", start=5, text=" world")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello world"
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0
        assert new_labels[0].label_end == 5

    def test_insert_empty_string_is_noop(self):
        text = "Hello"
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="insert", start=2, text="")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello"
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0

    def test_insert_out_of_bounds_raises(self):
        text = "Hello"
        op = TextOp(op="insert", start=10, text="x")

        with pytest.raises(ValueError, match="out of bounds"):
            apply_text_op(text, op, [])

    def test_insert_negative_start_raises(self):
        text = "Hello"
        op = TextOp(op="insert", start=-1, text="x")

        with pytest.raises(ValueError, match="out of bounds"):
            apply_text_op(text, op, [])

    def test_insert_label_ending_at_boundary_preserved(self):
        # Label ends at insert point → preserved (not shifted)
        text = "Hello world."
        labels = [_label("Hello", 0, 5)]
        op = TextOp(op="insert", start=5, text="XX")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "HelloXX world."
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 0
        assert new_labels[0].label_end == 5

    def test_insert_label_starting_at_boundary_shifts(self):
        # Label starts exactly at insert point → shifted
        text = "Hello world."
        labels = [_label("world", 6, 11)]
        op = TextOp(op="insert", start=6, text="XX")

        new_text, new_labels = apply_text_op(text, op, labels)

        assert new_text == "Hello XXworld."
        assert len(new_labels) == 1
        assert new_labels[0].label_start == 8
        assert new_labels[0].label_end == 13

    def test_insert_into_empty_text(self):
        text = ""
        op = TextOp(op="insert", start=0, text="Hello")

        new_text, new_labels = apply_text_op(text, op, [])

        assert new_text == "Hello"
        assert new_labels == []


# -------------------------------------------------------
# apply_text_ops — sequential
# -------------------------------------------------------


class TestApplyTextOps:
    def test_sequential_delete_then_insert(self):
        text = "Hello world."
        labels = [_label("Hello", 0, 5), _label("world", 6, 11)]
        ops = [
            TextOp(op="delete", start=0, text="Hello"),  # → " world."
            TextOp(op="insert", start=0, text="Greetings"),  # → "Greetings world."
        ]

        new_text, new_labels = apply_text_ops(text, ops, labels)

        assert new_text == "Greetings world."
        # "Hello" removed by delete (overlapping), "world" shifted
        assert len(new_labels) == 1
        assert new_labels[0].label_word == "world"
        # After delete: " world." → world at [1, 6)
        # After insert "Greetings" at 0: world shifts by 9 → [10, 15)
        assert new_labels[0].label_start == 10
        assert new_labels[0].label_end == 15

    def test_sequential_insert_then_delete(self):
        text = "AB"
        labels = [_label("AB", 0, 2)]
        ops = [
            TextOp(op="insert", start=1, text="XX"),  # → "AXXB", label shifts to [0,2)→gone because start<1 not end<=1
        ]

        new_text, new_labels = apply_text_ops(text, ops, labels)

        assert new_text == "AXXB"
        # Label "AB" [0,2): label_end=2 > start=1, but label_start=0 < start=1
        # Not in labels_to_move (start >= 1 → False), not in labels_to_preserve (end <= 1 → False)
        assert len(new_labels) == 0

    def test_empty_ops_is_noop(self):
        text = "Hello"
        labels = [_label("Hello", 0, 5)]

        new_text, new_labels = apply_text_ops(text, [], labels)

        assert new_text == "Hello"
        assert len(new_labels) == 1

    def test_invalid_second_op_raises(self):
        text = "Hello world."
        ops = [
            TextOp(op="delete", start=5, text=" world."),  # → "Hello"
            TextOp(op="delete", start=0, text="Hello world"),  # invalid: text is now "Hello"
        ]

        with pytest.raises(ValueError):
            apply_text_ops(text, ops, [])

    def test_multiple_inserts_accumulate(self):
        text = "AC"
        labels = [_label("A", 0, 1), _label("C", 1, 2)]
        ops = [
            TextOp(op="insert", start=1, text="B"),  # → "ABC", C shifts to [2,3)
            TextOp(op="insert", start=3, text="D"),  # → "ABCD"
        ]

        new_text, new_labels = apply_text_ops(text, ops, labels)

        assert new_text == "ABCD"
        a = next(lb for lb in new_labels if lb.label_word == "A")
        c = next(lb for lb in new_labels if lb.label_word == "C")
        assert a.label_start == 0
        assert a.label_end == 1
        assert c.label_start == 2
        assert c.label_end == 3
