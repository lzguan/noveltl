import logging
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.autolabels.constants import AutoLabelProgress, SepPriority
from src.autolabels.models import AutoLabel
from src.autolabels.params import CluenerParams
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from test_support.autolabels import DeterministicNERModel, RecordingDispatcher
from test_support.test_data.scenarios import DatabaseScenario

logger = logging.getLogger(__name__)


@pytest.fixture
def configured_autolabel_worker(
    test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    import src.autolabels.worker.tasks as worker_tasks

    engine = create_engine(test_url)
    monkeypatch.setattr(worker_tasks, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(worker_tasks, "get_ner_model", lambda model_name: DeterministicNERModel())
    yield
    engine.dispose()


class TestInsertAutoLabels:
    """Tests for insert_auto_labels service function (worker integration)."""

    @pytest.mark.asyncio
    async def test_basic(
        self,
        xianxia_scenario: DatabaseScenario,
        test_db: Session,
        recording_dispatcher: RecordingDispatcher,
        configured_autolabel_worker: None,
    ) -> None:
        from src.autolabels.worker.tasks import autolabel_infer

        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        ret = await insert_auto_labels(
            test_db,
            user,
            recording_dispatcher,
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

        assert len(recording_dispatcher.jobs) == len(chapters)
        for job_id, auto_label_id in recording_dispatcher.jobs:
            autolabel_infer(job_id, auto_label_id)

        test_db.expire_all()
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
        test_db: Session,
        recording_dispatcher: RecordingDispatcher,
    ) -> None:
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        await insert_auto_labels(
            test_db,
            user,
            recording_dispatcher,
            CreateAutoLabels(
                chapter_ids=[chapter.chapter_id for chapter in chapters],
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener", separators={"\n": SepPriority.HIGH}),
            ),
        )
        assert len(recording_dispatcher.jobs) == len(chapters)

    async def test_insert_twice_is_idempotent(
        self,
        xianxia_scenario: DatabaseScenario,
        test_db: Session,
        recording_dispatcher: RecordingDispatcher,
    ) -> None:
        novel = xianxia_scenario.novels["novel"]
        user = xianxia_scenario.users["owner"]
        chapters = [chapter for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")]
        ret = await insert_auto_labels(
            test_db,
            user,
            recording_dispatcher,
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
            recording_dispatcher,
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
        assert len(recording_dispatcher.jobs) == len(chapters) * 2
