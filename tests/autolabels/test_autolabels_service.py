import pytest
from typing import Protocol, Generator, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from arq import ArqRedis
from arq.worker import Worker

from src.autolabels.service import insert_auto_labels
from src.novels.models import Novel, RawChapter, RawChapterRevision
from src.autolabels.schemas import CreateAutoLabels
from src.autolabels.models import AutoLabel
from src.autolabels.utils import ArqDispatcher
from src.auth.models import User
from src.autolabels.constants import AutoLabelProgress


class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.mark.asyncio
@pytest.mark.slow
async def test_insert_auto_labels_basic(
    chinese_xianxia_small_test_novel : Novel, 
    chinese_xianxia_small_test_chapters : List[Tuple[RawChapter, RawChapterRevision]], 
    redis : ArqRedis, 
    db_session : Session, 
    sample_users : List[User], 
    worker_mock : Worker
):
    ret = await insert_auto_labels(
        db_session, 
        sample_users[0], 
        ArqDispatcher(redis), 
        CreateAutoLabels(
            raw_chapter_revision_ids=[revision.raw_chapter_revision_id for _, revision in chinese_xianxia_small_test_chapters],
            auto_label_model_name='cluener',
            auto_label_model_params={},
            novel_id=chinese_xianxia_small_test_novel.novel_id
        )
    )
    assert len(ret.inserts) == len(chinese_xianxia_small_test_chapters)
    print(ret.inserts)
    assert len(ret.exists) == 0
    print(ret.exists)

    await worker_mock.main()
    q = select(AutoLabel).where(AutoLabel.auto_label_id.in_([ret.inserts[a][0].auto_label_id for a in ret.inserts]))
    rows = db_session.execute(q).scalars().all()
    for row in rows:
        print(row.__dict__)
        assert row.auto_label_status == AutoLabelProgress.DONE