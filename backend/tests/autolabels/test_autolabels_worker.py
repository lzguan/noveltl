import logging

import pytest
from arq import ArqRedis
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.autolabels.constants import AutoLabelProgress, SepPriority
from src.autolabels.models import AutoLabel
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.autolabels.utils import ArqDispatcher
from tests.fixtures.bundles import ScenarioBundle
from tests.gate_logging import log_gate

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.dependency(
    depends=["gate::autolabels::utils"],
    scope="session",
)


class TestInsertAutoLabels:
    """Tests for insert_auto_labels service function (worker integration)."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.dependency(name="autolabels::worker::basic", scope="session")
    async def test_basic(
        self,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        redis: ArqRedis,
        test_db: Session,
        worker_mock: Worker,
    ):
        novel_bundle = chinese_xianxia_small_test_scenario.novels[0]
        ret = await insert_auto_labels(
            test_db,
            novel_bundle.user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter_bundle.chapter.chapter_id for chapter_bundle in novel_bundle.chapters],
                auto_label_model_name="cluener",
                auto_label_model_params={},
                novel_id=novel_bundle.novel.novel_id,
            ),
        )
        assert len(novel_bundle.chapters) > 0
        assert len(ret) == len(novel_bundle.chapters)
        logger.info("ret.inserts: %s", ret)
        assert all(a.auto_label_status == AutoLabelProgress.PENDING for a in ret)

        await worker_mock.main()
        q = select(AutoLabel).where(AutoLabel.auto_label_id.in_([a.auto_label_id for a in ret]))
        rows = test_db.execute(q).scalars().all()
        for row in rows:
            logger.info("AutoLabel row: %s", row.__dict__)
            assert row.auto_label_status == AutoLabelProgress.DONE

    @pytest.mark.dependency(name="autolabels::worker::set_params", scope="session")
    async def test_set_params(
        self,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        redis: ArqRedis,
        test_db: Session,
    ):
        novel_bundle = chinese_xianxia_small_test_scenario.novels[0]
        await insert_auto_labels(
            test_db,
            novel_bundle.user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter_bundle.chapter.chapter_id for chapter_bundle in novel_bundle.chapters],
                auto_label_model_name="cluener",
                auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
                novel_id=novel_bundle.novel.novel_id,
            ),
        )

    @pytest.mark.dependency(name="autolabels::worker::insert_twice_is_idempotent", scope="session")
    async def test_insert_twice_is_idempotent(
        self,
        chinese_xianxia_small_test_scenario: ScenarioBundle,
        redis: ArqRedis,
        test_db: Session,
    ):
        novel_bundle = chinese_xianxia_small_test_scenario.novels[0]
        ret = await insert_auto_labels(
            test_db,
            novel_bundle.user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter_bundle.chapter.chapter_id for chapter_bundle in novel_bundle.chapters],
                auto_label_model_name="cluener",
                auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
                novel_id=novel_bundle.novel.novel_id,
            ),
        )
        q = select(AutoLabel)
        result_rows = test_db.execute(q).scalars().all()
        assert len(result_rows) == len(novel_bundle.chapters)
        assert all(row.auto_label_status == AutoLabelProgress.PENDING for row in result_rows)
        assert len(ret) == len(novel_bundle.chapters)
        ret = await insert_auto_labels(
            test_db,
            novel_bundle.user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter_bundle.chapter.chapter_id for chapter_bundle in novel_bundle.chapters],
                auto_label_model_name="cluener",
                auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
                novel_id=novel_bundle.novel.novel_id,
            ),
        )
        assert len(ret) == 0
        result_rows = test_db.execute(q).scalars().all()
        assert len(result_rows) == len(novel_bundle.chapters)

    @pytest.mark.slow
    @pytest.mark.dependency(
        name="gate::autolabels::worker::insert_auto_labels",
        depends=[
            "autolabels::worker::basic",
            "autolabels::worker::set_params",
            "autolabels::worker::insert_twice_is_idempotent",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.slow
@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::autolabels::worker",
    depends=[
        "gate::autolabels::worker::insert_auto_labels",
    ],
    scope="session",
)
def test_gate():
    """All autolabels worker tests must pass before downstream layers run."""
    log_gate("gate::autolabels::worker")
