"""
Data-driven integration tests for modify_chapter_content.

Uses the committed synthetic catalog to load chapter text and autolabel data,
then compares in-memory apply_text_ops results against the service function's
DB output.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.labels.constants import LabelRole
from src.labels.models import Label as LabelModel
from src.labels.models import LabelContributor, LabelData, LabelGroup
from src.labels.schemas import Label as LabelSchema
from src.novels.models import ChapterContent
from src.novels.schemas import TextOp
from src.novels.service import modify_chapter_content
from src.novels.utils import apply_text_ops
from test_support.test_data import NovelDataset
from test_support.test_data.scenarios import DatabaseScenario


@pytest.fixture
def dd_label_group(
    test_db: Session,
    xianxia_scenario: DatabaseScenario,
) -> LabelGroup:
    """Create a label group for the test novel."""
    group = LabelGroup(
        label_group_name="Data Driven Test Group",
        novel_id=xianxia_scenario.novels["novel"].novel_id,
    )
    test_db.add(group)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=group.label_group_id,
            user_id=xianxia_scenario.users["owner"].user_id,
            label_contributor_role=LabelRole.OWNER,
        )
    )
    test_db.commit()
    return group


@pytest.fixture
def dd_chapter_0_labels(
    test_db: Session,
    xianxia_scenario: DatabaseScenario,
    xianxia_test_dataset: NovelDataset,
    dd_label_group: LabelGroup,
) -> tuple[ChapterContent, list[LabelModel]]:
    """
    Load autolabel data for chapter 0 and insert as real Labels in the DB.
    Returns the ChapterContent and the created labels.
    """
    cc = xianxia_scenario.contents["novel:xianxia-source-chapter-0001-v0002"]

    chapter_dataset = next(
        chapter for chapter in xianxia_test_dataset.chapters if chapter.id == "xianxia-source-chapter-0001"
    )
    version = next(item for item in chapter_dataset.versions if item.id == "xianxia-source-chapter-0001-v0002")
    artifact = next(item for item in version.artifacts if item.id == "xianxia-source-chapter-0001-v0002-cluener-output")
    auto_labels = artifact.labels

    # Create LabelData
    ld = LabelData(
        label_group_id=dd_label_group.label_group_id,
        chapter_content_id=cc.chapter_content_id,
    )
    test_db.add(ld)
    test_db.commit()

    # Create Labels from autolabel data
    labels: list[LabelModel] = []
    for al in auto_labels:
        label = LabelModel(
            label_data_id=ld.label_data_id,
            label_entity_group=al.entity_group,
            label_word=al.text,
            label_start=al.start,
            label_end=al.end,
            label_score=al.score,
            label_dirty=False,
        )
        labels.append(label)
    test_db.add_all(labels)
    test_db.commit()

    return cc, labels


class TestDataDrivenModifyChapterContent:
    def test_multiple_ops_match_in_memory(
        self,
        test_db: Session,
        xianxia_scenario: DatabaseScenario,
        dd_chapter_0_labels: tuple[ChapterContent, list[LabelModel]],
    ):
        """
        Apply multiple operations (delete first line, insert prefix) and verify match.
        """
        chapter = xianxia_scenario.chapters["novel:xianxia-source-chapter-0001"]
        cc = xianxia_scenario.contents["novel:xianxia-source-chapter-0001-v0002"]
        _, db_labels = dd_chapter_0_labels

        original_text = cc.chapter_content_text
        first_line = original_text.split("\n")[0] + "\n"
        ops = [
            TextOp(op="delete", start=0, text=first_line),
            TextOp(op="insert", start=0, text="\u65b0\u6807\u9898\n"),
        ]

        # In-memory
        in_memory_labels = [LabelSchema.model_validate(lb) for lb in db_labels]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service
        modify_chapter_content(
            test_db,
            xianxia_scenario.users["owner"],
            chapter.chapter_id,
            cc.chapter_content_id,
            ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == cc.chapter_content_version + 1,
            )
        ).scalar_one()

        assert new_cc.chapter_content_text == expected_text

        new_lds = (
            test_db.execute(select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id))
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
