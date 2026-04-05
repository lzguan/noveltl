import logging
from typing import Any

import pytest  # type: ignore
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth import models as auth_models
from src.autolabels import models as autolabel_models
from src.labels import models as label_models
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from src.novels import models as novel_models

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.dependency(
    depends=["gate::labels::permissions", "gate::novels::permissions"],
    scope="session",
)


class TestInsertLabelDatasByAutolabels:
    """Tests for insert_label_datas_by_autolabels cross-module operation."""

    @pytest.mark.order(1)
    @pytest.mark.dependency(name="insert_label_datas_by_autolabels", scope="session")
    @pytest.mark.dependency(name="labels::integration::insert_label_datas_by_autolabels", scope="session")
    def test_basic(
        self,
        chinese_xianxia_small_test_autolabels_cluener: list[autolabel_models.AutoLabel],
        chinese_xianxia_small_test_label_group: label_models.LabelGroup,
        chinese_xianxia_small_test_chapters: list[tuple[novel_models.Chapter, novel_models.ChapterContent]],
        chinese_xianxia_small_test_novel: novel_models.Novel,
        chinese_xianxia_small_test_default_params_cluener: dict[str, Any],
        chinese_xianxia_small_test_user: auth_models.User,
        chinese_xianxia_small_test_label_contributor: label_models.LabelContributor,
        chinese_xianxia_small_test_contributor: novel_models.NovelContributor,
        test_db: Session,
    ):
        # this test is AI generated.
        request = CreateLabelDataByAutoLabel(model_name='cluener', model_params=chinese_xianxia_small_test_default_params_cluener)
        res = insert_label_datas_by_autolabels(test_db, chinese_xianxia_small_test_user, chinese_xianxia_small_test_label_group.label_group_id, request)

        assert len(res.errors) == 0, f"Expected 0 errors, got: {res.errors}"
        expected_count = len(chinese_xianxia_small_test_autolabels_cluener)
        logger.info(f"Expecting {expected_count} successes, have {len(res.success)} successes + {len(res.errors)} failures")
        assert len(res.success) == expected_count

        source_revision_ids = {al.chapter_content_id for al in chinese_xianxia_small_test_autolabels_cluener}
        assert {s[1] for s in res.success} == source_revision_ids

        label_datas_in_db = test_db.execute(
            select(label_models.LabelData).where(
                label_models.LabelData.label_group_id == chinese_xianxia_small_test_label_group.label_group_id
            )
        ).scalars().all()
        assert len(label_datas_in_db) == expected_count

        source_data_map = {
            al.chapter_content_id: al.auto_label_data
            for al in chinese_xianxia_small_test_autolabels_cluener
        }

        for label_data in label_datas_in_db:
            assert label_data.chapter_content_id in source_data_map
            source_labels = source_data_map[label_data.chapter_content_id]

            db_labels = test_db.execute(
                select(label_models.Label)
                .where(label_models.Label.label_data_id == label_data.label_data_id)
                .order_by(label_models.Label.label_start)  # Sorting ensures index alignment
            ).scalars().all()
            sorted_source_labels = sorted(source_labels, key=lambda x: x['label_start'])

            assert len(db_labels) == len(sorted_source_labels)

            for db_label, source_label in zip(db_labels, sorted_source_labels, strict=False):
                assert db_label.label_word == source_label['label_word']
                assert db_label.label_start == source_label['label_start']
                assert db_label.label_end == source_label['label_end']
                assert db_label.label_entity_group == source_label['label_entity_group']

                if 'label_score' in source_label:
                    assert db_label.label_score == pytest.approx(source_label['label_score'])  # type: ignore


    @pytest.mark.dependency(
        name="gate::labels::integration::insert_label_datas_by_autolabels",
        depends=[
            "insert_label_datas_by_autolabels",
            "labels::integration::insert_label_datas_by_autolabels",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::labels::integration",
    depends=[
        "gate::labels::integration::insert_label_datas_by_autolabels",
    ],
    scope="session",
)
def test_gate():
    """All labels integration tests must pass before downstream layers run."""
    pass
