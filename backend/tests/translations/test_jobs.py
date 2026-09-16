from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork
from src.translations.models import (
    TranslationBatch,
    TranslationJob,
    TranslationJobChapter,
    TranslationStage,
    TranslationTask,
)
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus


def test_create_job_builds_batched_pipeline_from_latest_chapter_contents(test_db: Session) -> None:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Translation source")
    test_db.add_all([language, source_work])
    test_db.flush()
    novel = Novel(
        novel_title="Source novel",
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()

    chapters = [
        Chapter(
            chapter_num=chapter_num,
            chapter_title=f"Chapter {chapter_num}",
            chapter_is_public=False,
            novel_id=novel.novel_id,
        )
        for chapter_num in range(1, 6)
    ]
    test_db.add_all(chapters)
    test_db.flush()
    old_content = ChapterContent(
        chapter_id=chapters[1].chapter_id,
        chapter_content_text="Old chapter 2",
        chapter_content_version=1,
    )
    latest_contents = [
        ChapterContent(
            chapter_id=chapter.chapter_id,
            chapter_content_text=f"Chapter {chapter.chapter_num}",
            chapter_content_version=2 if chapter.chapter_num == 2 else 1,
        )
        for chapter in chapters
    ]
    test_db.add_all([old_content, *latest_contents])
    test_db.commit()

    request = TranslationJobCreate(
        novel_id=novel.novel_id,
        config={
            "start_chapter_num": 2,
            "end_chapter_num": 5,
            "batch_size": 2,
        },
        stages=[
            {"action": "prune_memories", "config": {"model": "qwen-plus", "memory_group_id": uuid4()}},
            {"action": "combine_chapter"},
            {"action": "translate_with_memories", "config": {"model": "qwen-plus"}},
        ],
    )
    job_id = create_job(test_db, request)

    job = test_db.get(TranslationJob, job_id)
    assert job is not None
    assert job.config == {
        "start_chapter_num": 2,
        "end_chapter_num": 5,
        "batch_size": 2,
    }

    stages = test_db.scalars(
        select(TranslationStage).where(TranslationStage.job_id == job_id).order_by(TranslationStage.stage_num)
    ).all()
    assert [(stage.stage_num, stage.action) for stage in stages] == [
        (0, "prune_memories"),
        (1, "combine_chapter"),
        (2, "translate_with_memories"),
    ]

    batches = test_db.scalars(
        select(TranslationBatch).where(TranslationBatch.job_id == job_id).order_by(TranslationBatch.batch_num)
    ).all()
    assert [batch.batch_num for batch in batches] == [0, 1]

    job_chapters = test_db.execute(
        select(TranslationJobChapter, Chapter.chapter_num)
        .join(Chapter, Chapter.chapter_id == TranslationJobChapter.chapter_id)
        .where(TranslationJobChapter.job_id == job_id)
        .order_by(Chapter.chapter_num)
    ).all()
    assert [
        (
            chapter_num,
            job_chapter.source_chapter_content_id,
            job_chapter.batch_id,
        )
        for job_chapter, chapter_num in job_chapters
    ] == [
        (2, latest_contents[1].chapter_content_id, batches[0].batch_id),
        (3, latest_contents[2].chapter_content_id, batches[0].batch_id),
        (4, latest_contents[3].chapter_content_id, batches[1].batch_id),
    ]

    tasks = test_db.execute(
        select(TranslationTask, TranslationStage.stage_num, TranslationBatch.batch_num)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .join(TranslationBatch, TranslationBatch.batch_id == TranslationTask.batch_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationStage.stage_num, TranslationBatch.batch_num)
    ).all()
    assert [(stage_num, batch_num, task.status) for task, stage_num, batch_num in tasks] == [
        (0, 0, TranslationTaskStatus.READY),
        (0, 1, TranslationTaskStatus.READY),
        (1, 0, TranslationTaskStatus.WAITING),
        (1, 1, TranslationTaskStatus.WAITING),
        (2, 0, TranslationTaskStatus.WAITING),
        (2, 1, TranslationTaskStatus.WAITING),
    ]
