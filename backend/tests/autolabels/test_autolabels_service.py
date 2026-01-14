import logging
from collections.abc import Generator
from typing import Protocol

import pytest
from arq import ArqRedis
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.autolabels.constants import AutoLabelProgress
from src.autolabels.models import AutoLabel
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.autolabels.utils import ArqDispatcher
from src.novels.models import Novel, RawChapter, RawChapterRevision

logger = logging.getLogger(__name__)

class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.mark.asyncio
@pytest.mark.slow
async def test_insert_auto_labels_basic(
    chinese_xianxia_small_test_novel : Novel,
    chinese_xianxia_small_test_chapters : list[tuple[RawChapter, RawChapterRevision]],
    redis : ArqRedis,
    test_db : Session,
    chinese_xianxia_small_test_user : User,
    worker_mock : Worker
):
    ret = await insert_auto_labels(
        test_db,
        chinese_xianxia_small_test_user,
        ArqDispatcher(redis),
        CreateAutoLabels(
            raw_chapter_revision_ids=[revision.raw_chapter_revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )
    assert len(ret.inserts) == len(chinese_xianxia_small_test_chapters)
    logger.info("ret.inserts: %s", ret.inserts)
    assert len(ret.exists) == 0
    logger.info("ret.exists: %s", ret.exists)

    await worker_mock.main()
    q = select(AutoLabel).where(AutoLabel.auto_label_id.in_([ret.inserts[a][0].auto_label_id for a in ret.inserts]))
    rows = test_db.execute(q).scalars().all()
    for row in rows:
        logger.info("AutoLabel row: %s", row.__dict__)
        assert row.auto_label_status == AutoLabelProgress.DONE
