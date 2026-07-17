import logging

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.labels import models as label_models
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from tests.fixtures.bundles import ScenarioBundle
from tests.gate_logging import log_gate

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.dependency(
    depends=["gate::labels::permissions", "gate::novels::permissions"],
    scope="session",
)


class TestInsertLabelDatasByAutolabels:
    """Tests for insert_label_datas_by_autolabels cross-module operation."""

    @pytest.mark.order(1)
    @pytest.mark.dependency(name="labels::integration::insert_label_datas_by_autolabels", scope="session")
    def test_basic(
        self,
        xianxia_autolabels_scenario: ScenarioBundle,
        test_db: Session,
    ):
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        label_bundle = xianxia_autolabels_scenario.label_groups[0]
        request = CreateLabelDataByAutoLabel(
            run_id=novel_bundle.autolabel_runs_by_name["cluener"].run_id,
        )
        # Opening a new group in the editor lazily creates an empty LabelData for
        # the active chapter before promotion begins.
        first_autolabel = novel_bundle.autolabels_by_name["cluener"][0]
        preexisting_label_data = label_models.LabelData(
            label_group_id=label_bundle.label_group.label_group_id,
            chapter_content_id=first_autolabel.chapter_content_id,
        )
        test_db.add(preexisting_label_data)
        test_db.commit()
        test_db.refresh(preexisting_label_data)

        res = insert_label_datas_by_autolabels(
            test_db,
            novel_bundle.user,
            label_bundle.label_group.label_group_id,
            request,
        )

        assert len(res.errors) == 0, f"Expected 0 errors, got: {res.errors}"
        expected_count = len(novel_bundle.autolabels_by_name["cluener"])
        logger.info(
            f"Expecting {expected_count} successes, have {len(res.success)} successes + {len(res.errors)} failures"
        )
        assert len(res.success) == expected_count

        source_revision_ids = {autolabel.chapter_content_id for autolabel in novel_bundle.autolabels_by_name["cluener"]}
        assert {s[1] for s in res.success} == source_revision_ids

        label_datas_in_db = (
            test_db.execute(
                select(label_models.LabelData).where(
                    label_models.LabelData.label_group_id == label_bundle.label_group.label_group_id
                )
            )
            .scalars()
            .all()
        )
        assert len(label_datas_in_db) == expected_count
        assert any(label_data.label_data_id == preexisting_label_data.label_data_id for label_data in label_datas_in_db)

        source_data_map = {
            al.chapter_content_id: al.auto_label_data for al in novel_bundle.autolabels_by_name["cluener"]
        }

        for label_data in label_datas_in_db:
            assert label_data.chapter_content_id in source_data_map
            source_labels = source_data_map[label_data.chapter_content_id]

            db_labels = (
                test_db.execute(
                    select(label_models.Label)
                    .where(label_models.Label.label_data_id == label_data.label_data_id)
                    .order_by(label_models.Label.label_start)  # Sorting ensures index alignment
                )
                .scalars()
                .all()
            )
            if source_labels is None:
                assert len(db_labels) == 0
                continue
            sorted_source_labels = sorted(source_labels, key=lambda x: x["label_start"])

            assert len(db_labels) == len(sorted_source_labels)

            for db_label, source_label in zip(db_labels, sorted_source_labels, strict=False):
                assert db_label.label_word == source_label["label_word"]
                assert db_label.label_start == source_label["label_start"]
                assert db_label.label_end == source_label["label_end"]
                assert db_label.label_entity_group == source_label["label_entity_group"]

                if "label_score" in source_label:
                    assert db_label.label_score == pytest.approx(source_label["label_score"])  # type: ignore

    @pytest.mark.dependency(
        name="gate::labels::integration::insert_label_datas_by_autolabels",
        depends=[
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
    log_gate("gate::labels::integration")
