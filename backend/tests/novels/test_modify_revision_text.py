"""
Integration tests for modify_chapter_content service function.

Uses the text_ops populator (to_* fixtures) with manually crafted data.
Text: "Hello world. This is a test sentence."
Labels group 1: "Hello" [0,5), "world" [6,11), "test" [22,26)
Labels group 2: "sentence" [27,35)
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.exceptions import InsufficientPermissionsException
from src.labels.models import Label as LabelModel
from src.labels.models import LabelData, LabelGroup
from src.novels.exceptions import ChapterContentOutdatedException
from src.novels.models import Chapter, ChapterContent
from src.novels.schemas import TextOp
from src.novels.service import modify_chapter_content


class TestBasicTextModification:

    def test_delete_shifts_labels_and_creates_new_version(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
        to_labels_2: list[LabelModel],
        to_label_group_1: LabelGroup,
        to_label_group_2: LabelGroup,
    ):
        ops = [TextOp(op="delete", start=0, text="Hello ")]  # delete "Hello "

        result = modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id, ops,
        )
        assert result.status == "success"

        # New chapter content should exist with version 2
        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "world. This is a test sentence."

        # Old chapter content unchanged
        old_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_content_id == to_chapter_content.chapter_content_id,
            )
        ).scalar_one()
        assert old_cc.chapter_content_text == "Hello world. This is a test sentence."
        assert old_cc.chapter_content_version == 1

        # Labels on new chapter content from group 1: "Hello" removed, "world" shifted, "test" shifted
        new_ld_1 = test_db.execute(
            select(LabelData).where(
                LabelData.chapter_content_id == new_cc.chapter_content_id,
                LabelData.label_group_id == to_label_group_1.label_group_id,
            )
        ).scalar_one()
        new_labels_1 = test_db.execute(
            select(LabelModel).where(LabelModel.label_data_id == new_ld_1.label_data_id)
        ).scalars().all()
        words_1 = {lb.label_word for lb in new_labels_1}
        assert "Hello" not in words_1  # overlaps deletion
        assert "world" in words_1
        assert "test" in words_1
        world = next(lb for lb in new_labels_1 if lb.label_word == "world")
        assert world.label_start == 0  # was 6, shifted left by 6
        assert world.label_end == 5
        test_label = next(lb for lb in new_labels_1 if lb.label_word == "test")
        assert test_label.label_start == 16  # was 22, shifted left by 6
        assert test_label.label_end == 20

        # Labels on new chapter content from group 2: "sentence" shifted
        new_ld_2 = test_db.execute(
            select(LabelData).where(
                LabelData.chapter_content_id == new_cc.chapter_content_id,
                LabelData.label_group_id == to_label_group_2.label_group_id,
            )
        ).scalar_one()
        new_labels_2 = test_db.execute(
            select(LabelModel).where(LabelModel.label_data_id == new_ld_2.label_data_id)
        ).scalars().all()
        assert len(new_labels_2) == 1
        assert new_labels_2[0].label_word == "sentence"
        assert new_labels_2[0].label_start == 21  # was 27, shifted left by 6
        assert new_labels_2[0].label_end == 29

    def test_insert_shifts_labels(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
    ):
        ops = [TextOp(op="insert", start=0, text="Dear ")]

        modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id, ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Dear Hello world. This is a test sentence."

        # All labels shifted right by 5
        new_ld = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalar_one()
        new_labels = test_db.execute(
            select(LabelModel).where(LabelModel.label_data_id == new_ld.label_data_id)
        ).scalars().all()
        assert len(new_labels) == 3
        hello = next(lb for lb in new_labels if lb.label_word == "Hello")
        assert hello.label_start == 5
        assert hello.label_end == 10

    def test_multiple_ops_applied_sequentially(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
    ):
        ops = [
            TextOp(op="delete", start=0, text="Hello "),  # -> "world. This is a test sentence."
            TextOp(op="insert", start=0, text="Greetings "),  # -> "Greetings world. This is a test sentence."
        ]

        modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id, ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Greetings world. This is a test sentence."


class TestEdgeCases:

    def test_empty_ops_creates_new_version_with_same_content(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
    ):
        modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id, [],
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Hello world. This is a test sentence."

        # Labels still ported
        new_ld = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalar_one()
        new_labels = test_db.execute(
            select(LabelModel).where(LabelModel.label_data_id == new_ld.label_data_id)
        ).scalars().all()
        assert len(new_labels) == 3

    def test_no_labels_on_chapter_content(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        # Note: no to_labels_* fixtures -> no labels exist
    ):
        ops = [TextOp(op="insert", start=0, text="New ")]

        result = modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id, ops,
        )
        assert result.status == "success"

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "New Hello world. This is a test sentence."

        # No label datas on new chapter content
        new_lds = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalars().all()
        assert len(new_lds) == 0


class TestStalenessChecks:

    def test_stale_chapter_content_id_raises(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
    ):
        # First call succeeds and creates version 2
        modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="A")],
        )

        # Second call with OLD chapter_content_id -> stale
        with pytest.raises(ChapterContentOutdatedException):
            modify_chapter_content(
                test_db, to_user, to_chapter.chapter_id,
                to_chapter_content.chapter_content_id,  # version 1, but version 2 exists
                [TextOp(op="insert", start=0, text="B")],
            )

    def test_successive_modifications_work(
        self,
        test_db: Session,
        to_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
        to_labels_1: list[LabelModel],
    ):
        # Create version 2
        modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="A")],
        )

        # Get the new chapter_content_id for version 2
        cc_v2 = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()

        # Create version 3 using version 2's id
        result = modify_chapter_content(
            test_db, to_user, to_chapter.chapter_id,
            cc_v2.chapter_content_id,
            [TextOp(op="insert", start=0, text="B")],
        )
        assert result.status == "success"

        cc_v3 = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 3,
            )
        ).scalar_one()
        assert cc_v3.chapter_content_text.startswith("BA")


class TestPermissions:

    def test_non_contributor_cannot_modify(
        self,
        test_db: Session,
        to_other_user: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
    ):
        # Select passes (public novel) but insert fails (not a contributor).
        # The error handler calls query_chapter_content_status which passes (public),
        # then falls through to InsufficientPermissionsException.
        with pytest.raises(InsufficientPermissionsException):
            modify_chapter_content(
                test_db, to_other_user, to_chapter.chapter_id,
                to_chapter_content.chapter_content_id,
                [TextOp(op="insert", start=0, text="X")],
            )
        # Verify text was NOT modified
        cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_content_id == to_chapter_content.chapter_content_id,
            )
        ).scalar_one()
        assert cc.chapter_content_text == "Hello world. This is a test sentence."
        # No version 2 should exist
        v2 = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == to_chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalars().first()
        assert v2 is None

    def test_admin_can_modify(
        self,
        test_db: Session,
        to_admin: User,
        to_chapter: Chapter,
        to_chapter_content: ChapterContent,
    ):
        result = modify_chapter_content(
            test_db, to_admin, to_chapter.chapter_id,
            to_chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="Admin ")],
        )
        assert result.status == "success"
