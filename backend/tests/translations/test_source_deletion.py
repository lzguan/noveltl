import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.novels.models import Chapter, ChapterContent
from src.novels.service import remove_chapter
from src.translations.models import TranslationBatch, TranslationJob, TranslationJobChapter, TranslationTask
from src.translations.schemas import TranslationJobCreate
from src.translations.service import create_translation_job
from test_support.test_data.scenarios import DatabaseScenario


@pytest.mark.parametrize("delete_revision", [False, True])
def test_deleting_translation_source_removes_only_its_association(
    test_db: Session, sample_scenario: DatabaseScenario, delete_revision: bool
) -> None:
    # Chapter deletion must remain usable after job creation. Translation jobs
    # retain their graph, accepting that missing sources may fail later work.
    chapters = [
        Chapter(
            novel_id=sample_scenario.novels["novel_1"].novel_id,
            chapter_num=number,
            chapter_title="Deletion test",
            chapter_is_public=False,
        )
        for number in (990, 991)
    ]
    test_db.add_all(chapters)
    test_db.flush()
    contents = [
        ChapterContent(chapter_id=c.chapter_id, chapter_content_version=1, chapter_content_text="Text")
        for c in chapters
    ]
    test_db.add_all(contents)
    test_db.commit()
    removed_id, retained_id = (c.chapter_id for c in chapters)
    content_id = contents[0].chapter_content_id
    user = sample_scenario.users["admin"]
    job_id = create_translation_job(
        test_db,
        user,
        TranslationJobCreate.model_validate(
            {
                "novel_id": sample_scenario.novels["novel_1"].novel_id,
                "config": {"start_chapter_num": 990, "end_chapter_num": 992, "batch_size": 10},
                "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}],
            }
        ),
    )
    if delete_revision:
        test_db.execute(delete(ChapterContent).where(ChapterContent.chapter_content_id == content_id))
        test_db.commit()
    else:
        assert remove_chapter(test_db, user, removed_id).status == "success"
    test_db.expire_all()
    assert (
        test_db.scalar(select(ChapterContent.chapter_content_id).where(ChapterContent.chapter_content_id == content_id))
        is None
    )
    assert list(
        test_db.scalars(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    ) == [retained_id]
    assert test_db.get(TranslationJob, job_id) is not None
    batch = test_db.scalar(select(TranslationBatch).where(TranslationBatch.job_id == job_id))
    assert batch is not None
    assert test_db.scalar(select(TranslationTask.task_id).where(TranslationTask.batch_id == batch.batch_id)) is not None
