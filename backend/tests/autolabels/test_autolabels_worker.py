import logging

import pytest
from arq import ArqRedis
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.autolabels.constants import AutoLabelProgress, SepPriority
from src.autolabels.models import AutoLabel
from src.autolabels.params import CluenerParams
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.autolabels.utils import ArqDispatcher
from test_support.test_data.scenarios import DatabaseScenario

logger = logging.getLogger(__name__)


class TestInsertAutoLabels:
    """Tests for insert_auto_labels service function (worker integration)."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_basic(
        self,
        xianxia_scenario: DatabaseScenario,
        redis: ArqRedis,
        test_db: Session,
        worker_mock: Worker,
    ):
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        ret = await insert_auto_labels(
            test_db,
            user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter.chapter_id for chapter in chapters],
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener"),
            ),
        )
        assert len(chapters) > 0
        assert len(ret.autolabels) == len(chapters)
        logger.info("ret.inserts: %s", ret)
        assert all(a.auto_label_meta.auto_label_status == AutoLabelProgress.PENDING for a in ret.autolabels)

        await worker_mock.main()
        q = select(AutoLabel).where(
            AutoLabel.auto_label_id.in_([a.auto_label_meta.auto_label_id for a in ret.autolabels])
        )
        rows = test_db.execute(q).scalars().all()
        for row in rows:
            logger.info("AutoLabel row: %s", row.__dict__)
            assert row.auto_label_status == AutoLabelProgress.DONE

    async def test_set_params(
        self,
        xianxia_scenario: DatabaseScenario,
        redis: ArqRedis,
        test_db: Session,
    ):
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        await insert_auto_labels(
            test_db,
            user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter.chapter_id for chapter in chapters],
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener", separators={"\n": SepPriority.HIGH}),
            ),
        )

    async def test_insert_twice_is_idempotent(
        self,
        xianxia_scenario: DatabaseScenario,
        redis: ArqRedis,
        test_db: Session,
    ):
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        ret = await insert_auto_labels(
            test_db,
            user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter.chapter_id for chapter in chapters],
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener", separators={"\n": SepPriority.HIGH}),
            ),
        )
        assert len(ret.autolabels) == len(chapters)
        assert all(a.auto_label_meta.auto_label_status == AutoLabelProgress.PENDING for a in ret.autolabels)

        # Second insert with the same params creates a new run — not
        # idempotent in the old sense, but each run is independent and
        # the unique constraint is (chapter_content_id, run_id).
        ret2 = await insert_auto_labels(
            test_db,
            user,
            ArqDispatcher(redis),
            CreateAutoLabels(
                chapter_ids=[chapter.chapter_id for chapter in chapters],
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener", separators={"\n": SepPriority.HIGH}),
            ),
        )
        assert len(ret2.autolabels) == len(chapters)

        # Total autolabels in DB should be double (two runs).
        q = select(AutoLabel)
        result_rows = test_db.execute(q).scalars().all()
        assert len(result_rows) == len(chapters) * 2
