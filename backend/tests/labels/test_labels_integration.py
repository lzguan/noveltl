import logging

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.autolabels.promotions.processing import process_promotion_job
from src.autolabels.schemas import CreateLabelDataByAutoLabel
from src.autolabels.service import create_promotion_job, query_promotion_failures
from src.labels import models as label_models
from test_support.autolabels import RecordingPromotionDispatcher
from test_support.test_data.scenarios import DatabaseScenario

logger = logging.getLogger(__name__)


class TestAutoLabelPromotion:
    async def test_basic(
        self,
        xianxia_autolabels_scenario: DatabaseScenario,
        test_db: Session,
        async_test_db: AsyncSession,
    ):
        run = xianxia_autolabels_scenario.autolabel_runs["cluener"]
        autolabels = xianxia_autolabels_scenario.autolabels
        label_group = xianxia_autolabels_scenario.label_groups["labels"]
        owner = xianxia_autolabels_scenario.users["owner"]
        request = CreateLabelDataByAutoLabel(
            run_id=run.run_id,
        )
        # Opening a new group in the editor lazily creates an empty LabelData for
        # the active chapter before promotion begins.
        first_autolabel = autolabels["xianxia-source-chapter-0001"]
        preexisting_label_data = label_models.LabelData(
            label_group_id=label_group.label_group_id,
            chapter_content_id=first_autolabel.chapter_content_id,
        )
        test_db.add(preexisting_label_data)
        test_db.commit()
        test_db.refresh(preexisting_label_data)
        preexisting_label_data_id = preexisting_label_data.label_data_id

        created = await create_promotion_job(
            async_test_db,
            owner,
            RecordingPromotionDispatcher(),
            label_group.label_group_id,
            request,
        )
        expected_count = len(autolabels)
        assert created.item_count == expected_count
        assert await process_promotion_job(async_test_db, created.promotion_id)
        failures = await query_promotion_failures(async_test_db, owner, created.promotion_id, limit=50, offset=0)
        assert failures == [], f"Expected 0 errors, got: {failures}"

        source_revision_ids = {autolabel.chapter_content_id for autolabel in autolabels.values()}
        test_db.expire_all()

        label_datas_in_db = (
            test_db.execute(
                select(label_models.LabelData).where(
                    label_models.LabelData.label_group_id == label_group.label_group_id
                )
            )
            .scalars()
            .all()
        )
        assert len(label_datas_in_db) == expected_count
        assert {label_data.chapter_content_id for label_data in label_datas_in_db} == source_revision_ids
        assert any(label_data.label_data_id == preexisting_label_data_id for label_data in label_datas_in_db)

        source_data_map = {al.chapter_content_id: al.auto_label_data for al in autolabels.values()}

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
                    assert db_label.label_score == pytest.approx(source_label["label_score"])
