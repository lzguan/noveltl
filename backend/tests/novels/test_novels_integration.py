"""Integration tests for modify_chapter_content using the bundled text-op scenario."""

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
from test_support.test_data.scenarios import DatabaseScenario


def _text_ops_user(scenario: DatabaseScenario, user_key: str) -> User:
    return scenario.users[user_key]


def _text_ops_chapter(scenario: DatabaseScenario) -> Chapter:
    return scenario.chapters["chapter"]


def _text_ops_chapter_content(scenario: DatabaseScenario) -> ChapterContent:
    return scenario.contents["content_v1"]


def _text_ops_label_group(scenario: DatabaseScenario, group_key: str) -> LabelGroup:
    return scenario.label_groups[group_key]


class TestBasicTextModification:
    def test_delete_shifts_labels_and_creates_new_version(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        label_group_1 = _text_ops_label_group(editing_scenario, "group_1")
        label_group_2 = _text_ops_label_group(editing_scenario, "group_2")
        ops = [TextOp(op="delete", start=0, text="Hello ")]  # delete "Hello "

        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            ops,
        )

        # New chapter content should exist with version 2
        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "world. This is a test sentence."

        # Old chapter content unchanged
        old_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_content_id == chapter_content.chapter_content_id,
            )
        ).scalar_one()
        assert old_cc.chapter_content_text == "Hello world. This is a test sentence."
        assert old_cc.chapter_content_version == 1

        # Labels on new chapter content from group 1: "Hello" removed, "world" shifted, "test" shifted
        new_ld_1 = test_db.execute(
            select(LabelData).where(
                LabelData.chapter_content_id == new_cc.chapter_content_id,
                LabelData.label_group_id == label_group_1.label_group_id,
            )
        ).scalar_one()
        new_labels_1 = (
            test_db.execute(select(LabelModel).where(LabelModel.label_data_id == new_ld_1.label_data_id))
            .scalars()
            .all()
        )
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
                LabelData.label_group_id == label_group_2.label_group_id,
            )
        ).scalar_one()
        new_labels_2 = (
            test_db.execute(select(LabelModel).where(LabelModel.label_data_id == new_ld_2.label_data_id))
            .scalars()
            .all()
        )
        assert len(new_labels_2) == 1
        assert new_labels_2[0].label_word == "sentence"
        assert new_labels_2[0].label_start == 21  # was 27, shifted left by 6
        assert new_labels_2[0].label_end == 29

    def test_insert_shifts_labels(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        label_group_1 = _text_ops_label_group(editing_scenario, "group_1")
        ops = [TextOp(op="insert", start=0, text="Dear ")]

        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Dear Hello world. This is a test sentence."

        # All labels shifted right by 5
        new_ld = test_db.execute(
            select(LabelData).where(
                LabelData.chapter_content_id == new_cc.chapter_content_id,
                LabelData.label_group_id == label_group_1.label_group_id,
            )
        ).scalar_one()
        new_labels = (
            test_db.execute(select(LabelModel).where(LabelModel.label_data_id == new_ld.label_data_id)).scalars().all()
        )
        assert len(new_labels) == 3
        hello = next(lb for lb in new_labels if lb.label_word == "Hello")
        assert hello.label_start == 5
        assert hello.label_end == 10

    def test_multiple_ops_applied_sequentially(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        ops = [
            TextOp(op="delete", start=0, text="Hello "),  # -> "world. This is a test sentence."
            TextOp(op="insert", start=0, text="Greetings "),  # -> "Greetings world. This is a test sentence."
        ]

        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Greetings world. This is a test sentence."


class TestEdgeCases:
    def test_empty_ops_creates_new_version_with_same_content(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        label_group_1 = _text_ops_label_group(editing_scenario, "group_1")
        label_group_2 = _text_ops_label_group(editing_scenario, "group_2")
        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            [],
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "Hello world. This is a test sentence."

        # Labels for both groups are still ported to the new version.
        new_label_datas = (
            test_db.execute(select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id))
            .scalars()
            .all()
        )
        assert len(new_label_datas) == 2

        group_1_label_data = next(
            label_data for label_data in new_label_datas if label_data.label_group_id == label_group_1.label_group_id
        )
        group_2_label_data = next(
            label_data for label_data in new_label_datas if label_data.label_group_id == label_group_2.label_group_id
        )

        group_1_labels = (
            test_db.execute(select(LabelModel).where(LabelModel.label_data_id == group_1_label_data.label_data_id))
            .scalars()
            .all()
        )
        group_2_labels = (
            test_db.execute(select(LabelModel).where(LabelModel.label_data_id == group_2_label_data.label_data_id))
            .scalars()
            .all()
        )
        assert len(group_1_labels) == 3
        assert len(group_2_labels) == 1

    def test_no_labels_on_chapter_content(self, test_db: Session, editing_scenario: DatabaseScenario):
        ops = [TextOp(op="insert", start=0, text="New ")]

        modify_chapter_content(
            test_db,
            editing_scenario.users["owner"],
            editing_scenario.chapters["unlabeled_chapter"].chapter_id,
            editing_scenario.contents["unlabeled_content_v1"].chapter_content_id,
            ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == editing_scenario.chapters["unlabeled_chapter"].chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()
        assert new_cc.chapter_content_text == "New Hello world. This is a test sentence."

        # No label datas on new chapter content
        new_lds = (
            test_db.execute(select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id))
            .scalars()
            .all()
        )
        assert len(new_lds) == 0


class TestStalenessChecks:
    def test_stale_chapter_content_id_raises(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        # First call succeeds and creates version 2
        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="A")],
        )

        # Second call with OLD chapter_content_id -> stale
        with pytest.raises(ChapterContentOutdatedException):
            modify_chapter_content(
                test_db,
                actor,
                chapter.chapter_id,
                chapter_content.chapter_content_id,  # version 1, but version 2 exists
                [TextOp(op="insert", start=0, text="B")],
            )

    def test_successive_modifications_work(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "owner")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        # Create version 2
        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="A")],
        )

        # Get the new chapter_content_id for version 2
        cc_v2 = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()

        # Create version 3 using version 2's id
        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            cc_v2.chapter_content_id,
            [TextOp(op="insert", start=0, text="B")],
        )

        cc_v3 = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 3,
            )
        ).scalar_one()
        assert cc_v3.chapter_content_text.startswith("BA")


class TestPermissions:
    def test_non_contributor_cannot_modify(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "other")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        # Select passes (public novel) but insert fails (not a contributor).
        # The error handler calls query_chapter_content_status which passes (public),
        # then falls through to InsufficientPermissionsException.
        with pytest.raises(InsufficientPermissionsException):
            modify_chapter_content(
                test_db,
                actor,
                chapter.chapter_id,
                chapter_content.chapter_content_id,
                [TextOp(op="insert", start=0, text="X")],
            )
        # Verify text was NOT modified
        cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_content_id == chapter_content.chapter_content_id,
            )
        ).scalar_one()
        assert cc.chapter_content_text == "Hello world. This is a test sentence."
        # No version 2 should exist
        v2 = (
            test_db.execute(
                select(ChapterContent).where(
                    ChapterContent.chapter_id == chapter.chapter_id,
                    ChapterContent.chapter_content_version == 2,
                )
            )
            .scalars()
            .first()
        )
        assert v2 is None

    def test_admin_can_modify(
        self,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ):
        actor = _text_ops_user(editing_scenario, "admin")
        chapter = _text_ops_chapter(editing_scenario)
        chapter_content = _text_ops_chapter_content(editing_scenario)
        modify_chapter_content(
            test_db,
            actor,
            chapter.chapter_id,
            chapter_content.chapter_content_id,
            [TextOp(op="insert", start=0, text="Admin ")],
        )
