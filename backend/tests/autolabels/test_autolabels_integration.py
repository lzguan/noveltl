import logging

import pytest
from arq import ArqRedis
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.autolabels.constants import AutoLabelProgress
from src.autolabels.models import AutoLabel
from src.autolabels.params import CluenerParams
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.autolabels.utils import ArqDispatcher
from src.labels import models as label_models
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from test_support.test_data.scenarios import DatabaseScenario

logger = logging.getLogger(__name__)


class TestAutolabelEndToEnd:
    """End-to-end test: novel + chapters → create autolabels → worker inference → promote to label data."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_flow(
        self,
        xianxia_scenario: DatabaseScenario,
        redis: ArqRedis,
        test_db: Session,
        worker_mock: Worker,
    ):
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        label_group = xianxia_scenario.label_groups["labels"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]

        chapter_ids = [chapter.chapter_id for chapter in chapters]
        assert len(chapter_ids) > 0

        # 1. Create autolabels.
        ret = await insert_auto_labels(
            test_db,
            user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=chapter_ids,
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener"),
            ),
        )
        run_id = ret.run.run_id

        assert len(ret.autolabels) == len(chapters)
        assert all(a.auto_label_meta.auto_label_status == AutoLabelProgress.PENDING for a in ret.autolabels)

        # 2. Run the worker to process all autolabels.
        await worker_mock.main()

        q = select(AutoLabel).where(AutoLabel.run_id == run_id)
        autolabel_rows = test_db.execute(q).scalars().all()
        assert len(autolabel_rows) == len(chapters)
        for row in autolabel_rows:
            assert row.auto_label_status == AutoLabelProgress.DONE
            assert row.auto_label_data is not None
            assert len(row.auto_label_data) > 0, f"Expected non-empty auto_label_data for autolabel {row.auto_label_id}"

        # 3. Promote autolabels to label data.
        promote_request = CreateLabelDataByAutoLabel(run_id=run_id)
        promote_result = insert_label_datas_by_autolabels(
            test_db,
            user,
            label_group.label_group_id,
            promote_request,
        )

        assert len(promote_result.errors) == 0, f"Expected 0 promotion errors, got: {promote_result.errors}"
        assert len(promote_result.success) == len(chapters)

        # 4. Verify label datas and labels are in the DB.
        label_datas = (
            test_db.execute(
                select(label_models.LabelData).where(
                    label_models.LabelData.label_group_id == label_group.label_group_id
                )
            )
            .scalars()
            .all()
        )
        assert len(label_datas) == len(chapters)

        # Build a map of autolabel data by chapter_content_id for verification.
        expected_data = {row.chapter_content_id: row.auto_label_data for row in autolabel_rows if row.auto_label_data}

        for label_data in label_datas:
            assert label_data.chapter_content_id in expected_data
            source_labels = expected_data[label_data.chapter_content_id]
            assert source_labels is not None

            db_labels = (
                test_db.execute(
                    select(label_models.Label)
                    .where(label_models.Label.label_data_id == label_data.label_data_id)
                    .order_by(label_models.Label.label_start)
                )
                .scalars()
                .all()
            )
            assert len(db_labels) == len(source_labels)

            sorted_source = sorted(source_labels, key=lambda x: x["label_start"])
            for db_label, src_label in zip(db_labels, sorted_source, strict=False):
                assert db_label.label_word == src_label["label_word"]
                assert db_label.label_start == src_label["label_start"]
                assert db_label.label_end == src_label["label_end"]
