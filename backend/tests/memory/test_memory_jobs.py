import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.agent.tasks.jobs import (
    JobParams,
    abort_job,
    claim_job,
    claim_next_task,
    claim_task,
    make_job,
    refresh_job,
    release_job,
    release_task,
)
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, Novel, SourceWork


def test_make_job_records_params_and_pending_tasks_for_chapter_range(test_db: Session) -> None:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory job source")
    test_db.add_all([language, source_work])
    test_db.flush()

    novel = Novel(
        novel_title="Memory job novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    other_novel = Novel(
        novel_title="Other novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add_all([novel, other_novel])
    test_db.flush()

    chapters = [
        Chapter(
            chapter_num=number,
            chapter_title=f"Chapter {number}",
            chapter_is_public=False,
            novel_id=novel.novel_id,
        )
        for number in range(1, 5)
    ]
    other_chapter = Chapter(
        chapter_num=2,
        chapter_title="Other chapter",
        chapter_is_public=False,
        novel_id=other_novel.novel_id,
    )
    memory_group = MemoryGroup(
        memory_group_name="Memory job group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add_all([*chapters, other_chapter, memory_group])
    test_db.commit()

    params = JobParams(model_name="deepseek:deepseek-chat", plugins=["glossary"])
    memory_job_id = make_job(test_db, memory_group.memory_group_id, 2, 4, params)

    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.memory_group_id == memory_group.memory_group_id
    assert job.job_params == params.model_dump(mode="json")

    tasks = test_db.scalars(
        select(MemoryChapterTask)
        .join(Chapter, Chapter.chapter_id == MemoryChapterTask.chapter_id)
        .where(MemoryChapterTask.memory_job_id == memory_job_id)
        .order_by(Chapter.chapter_num)
    ).all()
    assert [task.chapter_id for task in tasks] == [chapters[1].chapter_id, chapters[2].chapter_id]
    assert all(task.task_status == JobStatus.PENDING for task in tasks)
    assert all(task.attempt_count == 0 for task in tasks)

    first_token = uuid.uuid4()
    claimed_job = claim_job(test_db, memory_job_id, first_token, timedelta(minutes=5))
    assert claimed_job is not None
    assert claimed_job.claim_token == first_token
    assert claimed_job.job_params == params.model_dump(mode="json")

    second_token = uuid.uuid4()
    assert claim_job(test_db, memory_job_id, second_token, timedelta(minutes=5)) is None

    test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == memory_job_id)
        .values(claim_expires_at=func.now() - timedelta(seconds=1))
    )
    test_db.commit()
    reclaimed_job = claim_job(test_db, memory_job_id, second_token, timedelta(minutes=5))
    assert reclaimed_job is not None
    assert reclaimed_job.claim_token == second_token

    assert release_job(test_db, memory_job_id, first_token) is False
    test_db.refresh(reclaimed_job)
    assert reclaimed_job.claim_token == second_token

    assert release_job(test_db, memory_job_id, second_token) is True
    test_db.refresh(reclaimed_job)
    assert reclaimed_job.claim_token is None
    assert reclaimed_job.claim_expires_at is None

    third_token = uuid.uuid4()
    claimed_again = claim_job(test_db, memory_job_id, third_token, timedelta(minutes=5))
    assert claimed_again is not None
    assert claimed_again.claim_token == third_token
    assert refresh_job(test_db, memory_job_id, uuid.uuid4(), timedelta(minutes=5)) is False
    assert refresh_job(test_db, memory_job_id, third_token, timedelta(minutes=5)) is True

    assert abort_job(test_db, uuid.uuid4()) is False
    assert abort_job(test_db, memory_job_id) is True
    assert abort_job(test_db, memory_job_id) is True
    test_db.refresh(claimed_again)
    assert claimed_again.claim_token is None
    assert claimed_again.claim_expires_at is None
    assert release_job(test_db, memory_job_id, third_token) is False

    third_token = uuid.uuid4()
    claimed_again = claim_job(test_db, memory_job_id, third_token, timedelta(minutes=5))
    assert claimed_again is not None

    assert claim_next_task(test_db, memory_job_id, uuid.uuid4()) is None

    second_task = claim_task(test_db, memory_job_id, chapters[2].chapter_id, third_token)
    assert second_task is not None
    assert second_task.chapter_id == chapters[2].chapter_id
    assert second_task.task_status == JobStatus.PROCESSING
    assert second_task.attempt_count == 1
    assert claim_task(test_db, memory_job_id, chapters[2].chapter_id, third_token) is None
    assert (
        release_task(
            test_db,
            memory_job_id,
            second_task.chapter_id,
            second_token,
            JobStatus.COMPLETED,
        )
        is False
    )
    test_db.refresh(second_task)
    assert second_task.task_status == JobStatus.PROCESSING
    assert (
        release_task(
            test_db,
            memory_job_id,
            second_task.chapter_id,
            third_token,
            JobStatus.COMPLETED,
        )
        is True
    )

    first_task = claim_next_task(test_db, memory_job_id, third_token)
    assert first_task is not None
    assert first_task.chapter_id == chapters[1].chapter_id
    assert first_task.task_status == JobStatus.PROCESSING
    assert first_task.attempt_count == 1

    assert release_job(test_db, memory_job_id, second_token) is False
    test_db.refresh(first_task)
    assert first_task.task_status == JobStatus.PROCESSING

    assert (
        release_task(
            test_db,
            memory_job_id,
            first_task.chapter_id,
            third_token,
            JobStatus.FAILED,
        )
        is True
    )
    assert claim_next_task(test_db, memory_job_id, third_token) is None

    test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == memory_job_id)
        .values(claim_expires_at=func.now() - timedelta(seconds=1))
    )
    test_db.commit()
    assert refresh_job(test_db, memory_job_id, third_token, timedelta(minutes=5)) is False
    assert claim_job(test_db, memory_job_id, uuid.uuid4(), timedelta(minutes=5)) is None
