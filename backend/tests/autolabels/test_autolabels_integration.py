import asyncio
import logging
import os
import uuid
from collections.abc import Generator
from time import monotonic

import pytest
import redis
from celery.contrib.testing.worker import start_worker
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.autolabels.celery_app import app
from src.autolabels.constants import AutoLabelProgress
from src.autolabels.dispatch.celery import CeleryDispatcher
from src.autolabels.models import AutoLabel
from src.autolabels.params import CluenerParams
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.labels import models as label_models
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import insert_label_datas_by_autolabels
from test_support.autolabels import DeterministicNERModel
from test_support.test_data.scenarios import DatabaseScenario

logger = logging.getLogger(__name__)


class InlineCeleryDispatcher(CeleryDispatcher):
    """Celery dispatcher that avoids a thread hop in the in-process test worker."""

    async def aenqueue(self, job_id: uuid.UUID, auto_label_id: uuid.UUID) -> None:
        self.enqueue(job_id, auto_label_id)


@pytest.fixture
def celery_worker(
    test_url: str,
    test_db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    import src.autolabels.worker.tasks as worker_tasks

    redis_host = os.getenv("TEST_REDIS_HOST", "test_redis")
    redis_port = int(os.getenv("TEST_REDIS_PORT", "6379"))
    broker_url = f"redis://{redis_host}:{redis_port}/15"
    queue_name = f"autolabel-tests-{uuid.uuid4().hex}"
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=15)
    worker_engine = create_engine(test_url)

    redis_client.flushdb()
    monkeypatch.setattr(worker_tasks, "SessionLocal", sessionmaker(bind=worker_engine))
    monkeypatch.setattr(worker_tasks, "get_ner_model", lambda model_name: DeterministicNERModel())
    monkeypatch.setitem(app.conf, "broker_url", broker_url)
    monkeypatch.setitem(app.conf, "task_default_queue", queue_name)
    app.close()

    try:
        with start_worker(
            app,
            pool="solo",
            concurrency=1,
            queues=[queue_name],
            perform_ping_check=False,
            shutdown_timeout=10,
        ):
            yield
    finally:
        app.close()
        redis_client.flushdb()
        redis_client.close()
        worker_engine.dispose()


class TestAutolabelEndToEnd:
    """End-to-end test: novel + chapters → create autolabels → worker inference → promote to label data."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_flow(
        self,
        xianxia_scenario: DatabaseScenario,
        test_db: Session,
        celery_worker: None,
    ) -> None:
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
            InlineCeleryDispatcher(),
            CreateAutoLabels(
                chapter_ids=chapter_ids,
                novel_id=novel.novel_id,
                params=CluenerParams(model_name="cluener"),
            ),
        )
        run_id = ret.run.run_id

        assert len(ret.autolabels) == len(chapters)
        assert all(a.auto_label_meta.auto_label_status == AutoLabelProgress.PENDING for a in ret.autolabels)

        # 2. Wait for the Redis-backed Celery worker to process all autolabels.
        q = select(AutoLabel).where(AutoLabel.run_id == run_id)
        deadline = monotonic() + 15
        while monotonic() < deadline:
            test_db.expire_all()
            autolabel_rows = test_db.execute(q).scalars().all()
            if autolabel_rows and all(
                row.auto_label_status in (AutoLabelProgress.DONE, AutoLabelProgress.FAILED) for row in autolabel_rows
            ):
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("Celery worker did not finish autolabel jobs within 15 seconds.")

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
