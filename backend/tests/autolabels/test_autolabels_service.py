import logging
from collections.abc import Generator
from typing import Protocol

import pytest
from arq import ArqRedis
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.autolabels.constants import AutoLabelProgress, SepPriority
from src.autolabels.models import AutoLabel
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.service import insert_auto_labels
from src.autolabels.utils import ArqDispatcher
from src.novels.models import Chapter, Novel, Revision

logger = logging.getLogger(__name__)

class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.mark.asyncio
@pytest.mark.slow
async def test_insert_auto_labels_basic(
    chinese_xianxia_small_test_novel : Novel,
    chinese_xianxia_small_test_chapters : list[tuple[Chapter, Revision]],
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
            revision_ids=[revision.revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )
    assert len(chinese_xianxia_small_test_chapters) > 0 # move this to fixture test sometime in the future
    assert len(ret) == len(chinese_xianxia_small_test_chapters)
    logger.info("ret.inserts: %s", ret)
    assert all(a.auto_label_status == AutoLabelProgress.PENDING for a in ret)

    await worker_mock.main()
    q = select(AutoLabel).where(AutoLabel.auto_label_id.in_([a.auto_label_id for a in ret]))
    rows = test_db.execute(q).scalars().all()
    for row in rows:
        logger.info("AutoLabel row: %s", row.__dict__)
        assert row.auto_label_status == AutoLabelProgress.DONE

async def test_insert_auto_labels_set_params(
    chinese_xianxia_small_test_novel : Novel,
    chinese_xianxia_small_test_chapters : list[tuple[Chapter, Revision]],
    redis : ArqRedis,
    test_db : Session,
    chinese_xianxia_small_test_user : User
):
    await insert_auto_labels(
        test_db,
        chinese_xianxia_small_test_user,
        ArqDispatcher(redis),
        CreateAutoLabels(
            revision_ids=[revision.revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )

async def test_insert_auto_labels_twice(
    chinese_xianxia_small_test_novel : Novel,
    chinese_xianxia_small_test_chapters : list[tuple[Chapter, Revision]],
    redis : ArqRedis,
    test_db : Session,
    chinese_xianxia_small_test_user : User
):
    ret = await insert_auto_labels(
        test_db,
        chinese_xianxia_small_test_user,
        ArqDispatcher(redis),
        CreateAutoLabels(
            revision_ids=[revision.revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )
    q = select(AutoLabel)
    result_rows = test_db.execute(q).scalars().all()
    assert len(result_rows) == len(chinese_xianxia_small_test_chapters)
    assert all(row.auto_label_status == AutoLabelProgress.PENDING for row in result_rows)
    assert len(ret) == len(chinese_xianxia_small_test_chapters)
    ret = await insert_auto_labels(
        test_db,
        chinese_xianxia_small_test_user,
        ArqDispatcher(redis),
        CreateAutoLabels(
            revision_ids=[revision.revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={"separators": {"\n": SepPriority.HIGH}},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )
    assert len(ret) == 0
    result_rows = test_db.execute(q).scalars().all()
    assert len(result_rows) == len(chinese_xianxia_small_test_chapters)
