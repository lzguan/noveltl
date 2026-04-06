"""
Data-driven integration tests for modify_chapter_content.

Uses the chinese_xianxia_small_test populator to load real chapter text and
autolabel data, then compares in-memory apply_text_ops results against the
service function's DB output.
"""

import json

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
from tests.conftest import DataLoader
from tests.fixtures.bundles import ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::novels::service", "gate::novels::utils"],
    scope="session",
)


@pytest.fixture
def dd_label_group(
    test_db: Session,
    chinese_xianxia_small_test_scenario: ScenarioBundle,
) -> LabelGroup:
    """Create a label group for the test novel."""
    novel_bundle = chinese_xianxia_small_test_scenario.novels[0]
    group = LabelGroup(
        label_group_name="Data Driven Test Group",
        novel_id=novel_bundle.novel.novel_id,
    )
    test_db.add(group)
    test_db.commit()
    test_db.add(LabelContributor(
        label_group_id=group.label_group_id,
        user_id=novel_bundle.user.user_id,
        label_contributor_role=LabelRole.OWNER,
    ))
    test_db.commit()
    return group


@pytest.fixture
def dd_chapter_0_labels(
    test_db: Session,
    chinese_xianxia_small_test_scenario: ScenarioBundle,
    dd_label_group: LabelGroup,
    autolabel_loader: DataLoader,
) -> tuple[ChapterContent, list[LabelModel]]:
    """
    Load autolabel data for chapter 0 and insert as real Labels in the DB.
    Returns the ChapterContent and the created labels.
    """
    cc = chinese_xianxia_small_test_scenario.novels[0].chapters[0].latest_content

    # Load autolabel JSON for chapter 0
    autolabel_json = json.loads(next(autolabel_loader("chinese/chinese_xianxia/small_test/cluener")))
    auto_labels = autolabel_json["auto_label_data"]

    # Create LabelData
    ld = LabelData(
        label_group_id=dd_label_group.label_group_id,
        chapter_content_id=cc.chapter_content_id,
    )
    test_db.add(ld)
    test_db.commit()

    # Create Labels from autolabel data
    labels : list[LabelModel] = []
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

    return cc, labels


class TestDataDrivenModifyChapterContent:

    @pytest.mark.dependency(name="novels::integration_data::delete_substring_matches_in_memory", scope="session")
    def test_delete_substring_matches_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        dd_chapter_0_labels: tuple[ChapterContent, list[LabelModel]],
    ):
        """
        Delete the first line of chapter 0 and verify that the service function
        produces the same text and label positions as apply_text_ops in memory.
        """
        chapter_bundle = chinese_xianxia_small_test_scenario.novels[0].chapters[0]
        chapter, cc = chapter_bundle.chapter, chapter_bundle.latest_content
        _, db_labels = dd_chapter_0_labels

        original_text = cc.chapter_content_text
        # Delete the first line
        first_line = original_text.split("\n")[0] + "\n"
        ops = [TextOp(op="delete", start=0, text=first_line)]

        # In-memory computation
        in_memory_labels = [
            LabelSchema.model_validate(lb) for lb in db_labels
        ]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service function
        modify_chapter_content(
            test_db, chinese_xianxia_small_test_scenario.novels[0].user,
            chapter.chapter_id, cc.chapter_content_id, ops,
        )

        # Read back from DB
        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()

        assert new_cc.chapter_content_text == expected_text

        # Compare label positions
        new_lds = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalars().all()
        new_db_labels : list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(
                    select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)
                ).scalars().all()
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

    @pytest.mark.dependency(name="novels::integration_data::insert_text_matches_in_memory", scope="session")
    def test_insert_text_matches_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        dd_chapter_0_labels: tuple[ChapterContent, list[LabelModel]],
    ):
        """
        Insert text at the beginning of chapter 0 and verify service matches in-memory.
        """
        chapter_bundle = chinese_xianxia_small_test_scenario.novels[0].chapters[0]
        chapter, cc = chapter_bundle.chapter, chapter_bundle.latest_content
        _, db_labels = dd_chapter_0_labels

        original_text = cc.chapter_content_text
        insert_text = "\u3010\u7f16\u8005\u6ce8\u3011"
        ops = [TextOp(op="insert", start=0, text=insert_text)]

        # In-memory
        in_memory_labels = [LabelSchema.model_validate(lb) for lb in db_labels]
        expected_text, expected_labels = apply_text_ops(original_text, ops, in_memory_labels)

        # Service
        modify_chapter_content(
            test_db, chinese_xianxia_small_test_scenario.novels[0].user,
            chapter.chapter_id, cc.chapter_content_id, ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()

        assert new_cc.chapter_content_text == expected_text
        assert new_cc.chapter_content_text.startswith(insert_text)

        new_lds = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalars().all()
        new_db_labels : list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(
                    select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)
                ).scalars().all()
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

    @pytest.mark.dependency(name="novels::integration_data::multiple_ops_match_in_memory", scope="session")
    def test_multiple_ops_match_in_memory(
        self,
        test_db: Session,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        dd_chapter_0_labels: tuple[ChapterContent, list[LabelModel]],
    ):
        """
        Apply multiple operations (delete first line, insert prefix) and verify match.
        """
        chapter_bundle = chinese_xianxia_small_test_scenario.novels[0].chapters[0]
        chapter, cc = chapter_bundle.chapter, chapter_bundle.latest_content
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
            test_db, chinese_xianxia_small_test_scenario.novels[0].user,
            chapter.chapter_id, cc.chapter_content_id, ops,
        )

        new_cc = test_db.execute(
            select(ChapterContent).where(
                ChapterContent.chapter_id == chapter.chapter_id,
                ChapterContent.chapter_content_version == 2,
            )
        ).scalar_one()

        assert new_cc.chapter_content_text == expected_text

        new_lds = test_db.execute(
            select(LabelData).where(LabelData.chapter_content_id == new_cc.chapter_content_id)
        ).scalars().all()
        new_db_labels : list[LabelModel] = []
        for ld in new_lds:
            new_db_labels.extend(
                test_db.execute(
                    select(LabelModel).where(LabelModel.label_data_id == ld.label_data_id)
                ).scalars().all()
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

    @pytest.mark.dependency(
        name="gate::novels::integration_data::data_driven_modify_chapter_content",
        depends=[
            "novels::integration_data::delete_substring_matches_in_memory",
            "novels::integration_data::insert_text_matches_in_memory",
            "novels::integration_data::multiple_ops_match_in_memory",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::novels::integration_data",
    depends=[
        "gate::novels::integration_data::data_driven_modify_chapter_content",
    ],
    scope="session",
)
def test_gate():
    """All novels integration_data tests must pass before downstream layers run."""
    log_gate("gate::novels::integration_data")
