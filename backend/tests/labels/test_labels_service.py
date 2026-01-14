import logging

import pytest  # type: ignore

from src.auth import models as auth_models
from src.autolabels import models as autolabel_models
from src.labels import models as label_models
from src.labels.schemas import CreateLabelDataByAutoLabel
from src.labels.service import *
from src.novels import models as novel_models

logger = logging.getLogger(__name__)

def test_label_insert_label_data_by_autolabels_basic(
    chinese_xianxia_small_test_autolabels_cluener : List[autolabel_models.AutoLabel],
    chinese_xianxia_small_test_label_group : label_models.LabelGroup,
    chinese_xianxia_small_test_chapters : List[tuple[novel_models.RawChapter, novel_models.RawChapterRevision]],
    chinese_xianxia_small_test_novel : novel_models.Novel,
    chinese_xianxia_small_test_default_params_cluener : dict,
    chinese_xianxia_small_test_user : auth_models.User,
    chinese_xianxia_small_test_label_contributor : label_models.LabelContributor,
    chinese_xianxia_small_test_contributor : novel_models.Contributor,
    test_db : Session
):
    # this test is AI generated.
    request = CreateLabelDataByAutoLabel(model_name='cluener', model_params=chinese_xianxia_small_test_default_params_cluener)
    res = insert_label_datas_by_autolabels(test_db, chinese_xianxia_small_test_user, chinese_xianxia_small_test_label_group.label_group_id, request)

    assert len(res.errors) == 0, f"Expected 0 errors, got: {res.errors}"
    expected_count = len(chinese_xianxia_small_test_autolabels_cluener)
    logger.info(f"Expecting {expected_count} succeses, have {len(res.success)} succeses + {len(res.errors)} failures")
    assert len(res.success) == expected_count

    source_revision_ids = {al.raw_chapter_revision_id for al in chinese_xianxia_small_test_autolabels_cluener}
    assert set(res.success) == source_revision_ids

    label_datas_in_db = test_db.execute(
        select(label_models.LabelData).where(
            label_models.LabelData.label_group_id == chinese_xianxia_small_test_label_group.label_group_id
        )
    ).scalars().all()
    assert len(label_datas_in_db) == expected_count

    source_data_map = {
        al.raw_chapter_revision_id: al.auto_label_data
        for al in chinese_xianxia_small_test_autolabels_cluener
    }

    for label_data in label_datas_in_db:
        assert label_data.raw_chapter_revision_id in source_data_map
        source_labels = source_data_map[label_data.raw_chapter_revision_id]

        db_labels = test_db.execute(
            select(label_models.Label)
            .where(label_models.Label.label_data_id == label_data.label_data_id)
            .order_by(label_models.Label.label_start) # Sorting ensures index alignment
        ).scalars().all()
        sorted_source_labels = sorted(source_labels, key=lambda x: x['label_start'])

        assert len(db_labels) == len(sorted_source_labels)

        for db_label, source_label in zip(db_labels, sorted_source_labels):
            assert db_label.label_word == source_label['label_word']
            assert db_label.label_start == source_label['label_start']
            assert db_label.label_end == source_label['label_end']
            assert db_label.label_entity_group == source_label['label_entity_group']

            if 'label_score' in source_label:
                assert db_label.label_score == pytest.approx(source_label['label_score'])



## ---------------- Populate test data ---------------- ##

# from typing import Protocol, Generator
# from arq.worker import Worker
# from pathlib import Path

# class Loader(Protocol):
#     def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
#         ...

# @pytest.mark.asyncio
# async def test_chinese_xianxia_small_test_autolabels(chinese_xianxia_small_test_novel : Novel, chinese_xianxia_small_test_chapters : List[Tuple[RawChapter, RawChapterRevision]], autolabel_loader : Loader, test_db : Session, worker_mock : Worker, redis, sample_users : List[User]):
#     from src.autolabels.service import insert_auto_labels
#     from src.autolabels.utils import ArqDispatcher
#     from src.autolabels.schemas import CreateAutoLabels, AutoLabel
#     from sqlalchemy import select
#     import json

#     await insert_auto_labels(
#         test_db,
#         sample_users[0],
#         ArqDispatcher(redis),
#         CreateAutoLabels(
#             raw_chapter_revision_ids=[revision.raw_chapter_revision_id for _, revision in chinese_xianxia_small_test_chapters],
#             auto_label_model_name='cluener',
#             auto_label_model_params={},
#             novel_id=chinese_xianxia_small_test_novel.novel_id
#         )
#     )
#     await worker_mock.main()
#     q = select(
#         autolabel_models.AutoLabel,
#         RawChapter
#     ).select_from(
#         autolabel_models.AutoLabel
#     ).join(
#         RawChapterRevision,
#         RawChapterRevision.raw_chapter_revision_id == autolabel_models.AutoLabel.raw_chapter_revision_id
#     ).join(
#         RawChapter,
#         RawChapter.raw_chapter_id == RawChapterRevision.raw_chapter_id
#     )
#     path = Path(__file__).parent.parent / 'test_data' / 'autolabels' / 'chinese' / 'chinese_xianxia' / 'small_test' / 'cluener'
#     result = test_db.execute(q)
#     for a, c in result:
#         autolabel : AutoLabel = a
#         chapter : RawChapter = c
#         autolabel_schema = AutoLabel.model_validate(autolabel)
#         with open(path / f'chapter_{chapter.raw_chapter_num}.json', 'w') as f:
#             to_dump = autolabel_schema.model_dump()
#             del to_dump['auto_label_id']
#             del to_dump['raw_chapter_revision_id']
#             json.dump(to_dump, f)
## -------------------------------------------------- ##
