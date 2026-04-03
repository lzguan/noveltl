"""
Data-driven integration tests for modify_revision_text.

Uses the chinese_xianxia_small_test populator to load real chapter text and
autolabel data, then compares in-memory apply_text_ops results against the
service function's DB output.
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.labels.constants import LabelRole
from src.labels.models import Label as LabelModel
from src.labels.models import LabelContributor, LabelData, LabelGroup
from src.labels.schemas import Label as LabelSchema
from src.novels.models import Chapter, Contributor, Novel, Revision, RevisionText
from src.novels.schemas import TextOp
from src.novels.service import modify_revision_text
from src.novels.utils import apply_text_ops
from tests.conftest import DataLoader


@pytest.fixture
def dd_label_group(
    test_db: Session,
    chinese_xianxia_small_test_novel: Novel,
    chinese_xianxia_small_test_user: User,
) -> LabelGroup:
    """Create a label group for the test novel."""
    group = LabelGroup(
        label_group_name="Data Driven Test Group",
        novel_id=chinese_xianxia_small_test_novel.novel_id,
    )
    test_db.add(group)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=group.label_group_id,
            user_id=chinese_xianxia_small_test_user.user_id,
            label_contributor_role=LabelRole.OWNER,
        )
    )
    test_db.commit()
    return group


@pytest.fixture
def dd_chapter_0_labels(
    test_db: Session,
    chinese_xianxia_small_test_chapters: list[tuple[Chapter, Revision, RevisionText]],
    chinese_xianxia_small_test_contributor: Contributor,
    dd_label_group: LabelGroup,
    autolabel_loader: DataLoader,
) -> tuple[RevisionText, list[LabelModel]]:
    """
    Load autolabel data for chapter 0 and insert as real Labels in the DB.
    Returns the RevisionText and the created labels.
    """
    _, _, rt = chinese_xianxia_small_test_chapters[0]

    # Load autolabel JSON for chapter 0
    autolabel_json = json.loads(next(autolabel_loader("chinese/chinese_xianxia/small_test/cluener")))
    auto_labels = autolabel_json["auto_label_data"]

    # Create LabelData
    ld = LabelData(
        label_group_id=dd_label_group.label_group_id,
        revision_text_id=rt.revision_text_id,
    )
    test_db.add(ld)
    test_db.commit()

    # Create Labels from autolabel data
    labels: list[LabelModel] = []
    for al in auto_labels:
        label = LabelModel(
            label_data_id=ld.label_data_id,
            label_entity_group=al["label_entity_group"],
            label_word=al["label_word"],
            label_start=al["label_start"],
            label_end=al["label_end"],
            label_score=al["label_score"],
            label_dirty=al["label_dirty"],
        )
        labels.append(label)
    test_db.add_all(labels)
    test_db.commit()

    return rt, labels


class TestDataDrivenModifyRevisionText:
    def test_delete_substring_matches_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        chinese_xianxia_small_test_chapters: list[tuple[Chapter, Revision, RevisionText]],
        dd_chapter_0_labels: tuple[RevisionText, list[LabelModel]],
    ):
        """
        Delete the first line of chapter 0 and verify that the service function
        produces the same text and label positions as apply_text_ops in memory.
        """
        _, revision, rt = chinese_xianxia_small_test_chapters[0]
        _, db_labels = dd_chapter_0_labels

        original_text = rt.revision_text_content
        # Delete the first line "提笔有感\n"
        first_line = original_text.split("\n")[0] + "\n"
        ops = [TextOp(op="delete", start=0, text=first_line)]

        # In-memory computation
        in_memory_labels = [LabelSchema.model_validate(lb) for lb in db_labels]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service function
        modify_revision_text(
            test_db,
            chinese_xianxia_small_test_user,
            revision.revision_id,
            rt.revision_text_id,
            ops,
        )

        # Read back from DB
        new_rt = test_db.execute(
            select(RevisionText).where(
                RevisionText.revision_id == revision.revision_id,
                RevisionText.revision_text_version == 2,
            )
        ).scalar_one()

        assert new_rt.revision_text_content == expected_text

        # Compare label positions
        new_lds = (
            test_db.execute(select(LabelData).where(LabelData.revision_text_id == new_rt.revision_text_id))
            .scalars()
            .all()
        )
        new_db_labels: list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)).scalars().all()
            )

        assert len(new_db_labels) == len(expected_labels)

        # Sort both by label_start for comparison
        new_db_labels_sorted = sorted(new_db_labels, key=lambda lb: lb.label_start)
        expected_labels_sorted = sorted(expected_labels, key=lambda lb: lb.label_start)

        for db_label, mem_label in zip(new_db_labels_sorted, expected_labels_sorted, strict=True):
            assert db_label.label_word == mem_label.label_word
            assert db_label.label_start == mem_label.label_start
            assert db_label.label_end == mem_label.label_end
            assert db_label.label_entity_group == mem_label.label_entity_group

    def test_insert_text_matches_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        chinese_xianxia_small_test_chapters: list[tuple[Chapter, Revision, RevisionText]],
        dd_chapter_0_labels: tuple[RevisionText, list[LabelModel]],
    ):
        """
        Insert text at the beginning of chapter 0 and verify service matches in-memory.
        """
        _, revision, rt = chinese_xianxia_small_test_chapters[0]
        _, db_labels = dd_chapter_0_labels

        original_text = rt.revision_text_content
        insert_text = "【编者注】"
        ops = [TextOp(op="insert", start=0, text=insert_text)]

        # In-memory
        in_memory_labels = [LabelSchema.model_validate(lb) for lb in db_labels]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service
        modify_revision_text(
            test_db,
            chinese_xianxia_small_test_user,
            revision.revision_id,
            rt.revision_text_id,
            ops,
        )

        new_rt = test_db.execute(
            select(RevisionText).where(
                RevisionText.revision_id == revision.revision_id,
                RevisionText.revision_text_version == 2,
            )
        ).scalar_one()

        assert new_rt.revision_text_content == expected_text
        assert new_rt.revision_text_content.startswith(insert_text)

        new_lds = (
            test_db.execute(select(LabelData).where(LabelData.revision_text_id == new_rt.revision_text_id))
            .scalars()
            .all()
        )
        new_db_labels: list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)).scalars().all()
            )

        assert len(new_db_labels) == len(expected_labels)

        for db_l, mem_l in zip(
            sorted(new_db_labels, key=lambda lb: lb.label_start),
            sorted(expected_labels, key=lambda lb: lb.label_start),
            strict=True,
        ):
            assert db_l.label_word == mem_l.label_word
            assert db_l.label_start == mem_l.label_start
            assert db_l.label_end == mem_l.label_end

    def test_multiple_ops_match_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_user: User,
        chinese_xianxia_small_test_chapters: list[tuple[Chapter, Revision, RevisionText]],
        dd_chapter_0_labels: tuple[RevisionText, list[LabelModel]],
    ):
        """
        Apply multiple operations (delete first line, insert prefix) and verify match.
        """
        _, revision, rt = chinese_xianxia_small_test_chapters[0]
        _, db_labels = dd_chapter_0_labels

        original_text = rt.revision_text_content
        first_line = original_text.split("\n")[0] + "\n"
        ops = [
            TextOp(op="delete", start=0, text=first_line),
            TextOp(op="insert", start=0, text="新标题\n"),
        ]

        # In-memory
        in_memory_labels = [LabelSchema.model_validate(lb) for lb in db_labels]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service
        modify_revision_text(
            test_db,
            chinese_xianxia_small_test_user,
            revision.revision_id,
            rt.revision_text_id,
            ops,
        )

        new_rt = test_db.execute(
            select(RevisionText).where(
                RevisionText.revision_id == revision.revision_id,
                RevisionText.revision_text_version == 2,
            )
        ).scalar_one()

        assert new_rt.revision_text_content == expected_text

        new_lds = (
            test_db.execute(select(LabelData).where(LabelData.revision_text_id == new_rt.revision_text_id))
            .scalars()
            .all()
        )
        new_db_labels: list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)).scalars().all()
            )

        assert len(new_db_labels) == len(expected_labels)

        for db_l, mem_l in zip(
            sorted(new_db_labels, key=lambda lb: lb.label_start),
            sorted(expected_labels, key=lambda lb: lb.label_start),
            strict=True,
        ):
            assert db_l.label_word == mem_l.label_word
            assert db_l.label_start == mem_l.label_start
            assert db_l.label_end == mem_l.label_end
