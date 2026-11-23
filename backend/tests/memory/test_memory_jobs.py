import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.languages.models import Language
from src.memory.agent.config import JobParamsV1 as JobParams
from src.memory.agent.config import JobParamsV2
from src.memory.agent.tasks.jobs import (
    abort_job,
    claim_job,
    claim_next_task,
    claim_task,
    fail_task,
    make_job,
    refresh_job,
    release_job,
)
from src.memory.agent.tasks.schedule import StageBarrierSchedule
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, Novel, SourceWork


async def _complete_task(db: AsyncSession, memory_job_id: uuid.UUID, chapter_id: uuid.UUID, stage_num: int = 0) -> None:
    completed = await db.scalar(
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
            MemoryChapterTask.stage_num == stage_num,
            MemoryChapterTask.task_status == JobStatus.PROCESSING,
        )
        .values(task_status=JobStatus.COMPLETED)
        .returning(MemoryChapterTask.chapter_id)
    )
    assert completed is not None
    await db.commit()


async def test_make_job_records_params_and_pending_tasks_for_chapter_range(async_test_db: AsyncSession) -> None:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory job source")
    async_test_db.add_all([language, source_work])
    await async_test_db.flush()

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
    async_test_db.add_all([novel, other_novel])
    await async_test_db.flush()

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
    async_test_db.add_all([*chapters, other_chapter, memory_group])
    await async_test_db.commit()
    chapter_ids = [chapter.chapter_id for chapter in chapters]

    params = JobParams(
        model_name="deepseek:deepseek-v4-flash-low",
        toolsets={
            "glossary_terms": {},
            "glossary_definitions_read": {},
            "glossary_definitions_write": {},
            "glossary_relations_read": {},
            "glossary_relations_write": {},
            "glossary_character_read": {},
            "glossary_character_write": {},
            "glossary_events_read": {},
            "glossary_events_write": {},
        },
    )
    memory_job_id = await make_job(async_test_db, memory_group.memory_group_id, 2, 4, params)

    job = await async_test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.memory_group_id == memory_group.memory_group_id
    assert job.job_params == params.model_dump(mode="json")

    tasks = (
        await async_test_db.scalars(
            select(MemoryChapterTask)
            .join(Chapter, Chapter.chapter_id == MemoryChapterTask.chapter_id)
            .where(MemoryChapterTask.memory_job_id == memory_job_id)
            .order_by(Chapter.chapter_num)
        )
    ).all()
    assert [task.chapter_id for task in tasks] == [chapter_ids[1], chapter_ids[2]]
    assert all(task.task_status == JobStatus.PENDING for task in tasks)
    assert all(task.attempt_count == 0 for task in tasks)

    first_token = uuid.uuid4()
    claimed_job = await claim_job(async_test_db, memory_job_id, first_token, timedelta(minutes=5))
    assert claimed_job is not None
    assert claimed_job.claim_token == first_token
    assert claimed_job.job_params == params.model_dump(mode="json")

    second_token = uuid.uuid4()
    assert await claim_job(async_test_db, memory_job_id, second_token, timedelta(minutes=5)) is None

    await async_test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == memory_job_id)
        .values(claim_expires_at=func.now() - timedelta(seconds=1))
    )
    await async_test_db.commit()
    reclaimed_job = await claim_job(async_test_db, memory_job_id, second_token, timedelta(minutes=5))
    assert reclaimed_job is not None
    assert reclaimed_job.claim_token == second_token

    assert await release_job(async_test_db, memory_job_id, first_token) is False
    await async_test_db.refresh(reclaimed_job)
    assert reclaimed_job.claim_token == second_token

    assert await release_job(async_test_db, memory_job_id, second_token) is True
    await async_test_db.refresh(reclaimed_job)
    assert reclaimed_job.claim_token is None
    assert reclaimed_job.claim_expires_at is None

    third_token = uuid.uuid4()
    claimed_again = await claim_job(async_test_db, memory_job_id, third_token, timedelta(minutes=5))
    assert claimed_again is not None
    assert claimed_again.claim_token == third_token
    assert await refresh_job(async_test_db, memory_job_id, uuid.uuid4(), timedelta(minutes=5)) is False
    assert await refresh_job(async_test_db, memory_job_id, third_token, timedelta(minutes=5)) is True

    assert (await abort_job(async_test_db, uuid.uuid4())) is False
    assert await release_job(async_test_db, memory_job_id, third_token) is True

    third_token = uuid.uuid4()
    claimed_again = await claim_job(async_test_db, memory_job_id, third_token, timedelta(minutes=5))
    assert claimed_again is not None

    assert await claim_next_task(async_test_db, memory_job_id, uuid.uuid4(), StageBarrierSchedule()) is None

    second_task = await claim_task(async_test_db, memory_job_id, chapter_ids[2], third_token, StageBarrierSchedule())
    assert second_task is not None
    assert second_task.chapter_id == chapter_ids[2]
    assert second_task.task_status == JobStatus.PROCESSING
    assert second_task.attempt_count == 1
    assert await claim_task(async_test_db, memory_job_id, chapter_ids[2], third_token, StageBarrierSchedule()) is None
    assert (
        await fail_task(
            async_test_db,
            memory_job_id,
            second_task.chapter_id,
            second_token,
        )
        is False
    )
    await async_test_db.refresh(second_task)
    assert second_task.task_status == JobStatus.PROCESSING
    await _complete_task(async_test_db, memory_job_id, second_task.chapter_id)

    first_task = await claim_next_task(async_test_db, memory_job_id, third_token, StageBarrierSchedule())
    assert first_task is not None
    assert first_task.chapter_id == chapter_ids[1]
    assert first_task.task_status == JobStatus.PROCESSING
    assert first_task.attempt_count == 1

    # Processing work is recoverable from an expired lease, but an unclaimed
    # processing task is an invalid state and must not be silently adopted.
    assert await release_job(async_test_db, memory_job_id, third_token) is True
    replacement_token = uuid.uuid4()
    assert await claim_job(async_test_db, memory_job_id, replacement_token, timedelta(minutes=5)) is None

    stale_token = uuid.uuid4()
    await async_test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == memory_job_id)
        .values(
            claim_token=stale_token,
            claim_expires_at=func.now() - timedelta(seconds=1),
        )
    )
    await async_test_db.commit()

    assert await claim_job(async_test_db, memory_job_id, replacement_token, timedelta(minutes=5)) is not None
    reclaimed_task = await claim_next_task(async_test_db, memory_job_id, replacement_token, StageBarrierSchedule())
    assert reclaimed_task is not None
    assert reclaimed_task.chapter_id == first_task.chapter_id
    assert reclaimed_task.task_status == JobStatus.PROCESSING
    assert reclaimed_task.attempt_count == 2

    assert (await abort_job(async_test_db, memory_job_id)) is True
    await async_test_db.refresh(reclaimed_task)
    await async_test_db.refresh(claimed_again)
    assert reclaimed_task.task_status == JobStatus.FAILED
    assert claimed_again.claim_token is None
    assert claimed_again.claim_expires_at is None
    assert (
        await fail_task(
            async_test_db,
            memory_job_id,
            reclaimed_task.chapter_id,
            replacement_token,
        )
        is False
    )
    assert await claim_job(async_test_db, memory_job_id, uuid.uuid4(), timedelta(minutes=5)) is None


async def test_stages_run_as_job_wide_barriers(async_test_db: AsyncSession) -> None:
    """Naming relies on every chapter being recorded first, for whole-range context."""
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Barrier source")
    async_test_db.add_all([language, source_work])
    await async_test_db.flush()
    novel = Novel(
        novel_title="Barrier novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    async_test_db.add(novel)
    await async_test_db.flush()
    chapters = [
        Chapter(chapter_num=number, chapter_title=f"Chapter {number}", chapter_is_public=False, novel_id=novel.novel_id)
        for number in (1, 2)
    ]
    memory_group = MemoryGroup(
        memory_group_name="Barrier group", novel_id=novel.novel_id, memory_language=language.language_code
    )
    async_test_db.add_all([*chapters, memory_group])
    await async_test_db.commit()
    params = JobParamsV2.model_validate(
        {
            "record_memories": {"model_name": "deepseek:deepseek-v4-flash-low", "toolsets": {}},
            "translate_terms": {"model_name": "deepseek:deepseek-v4-flash-low"},
        }
    )
    memory_job_id = await make_job(async_test_db, memory_group.memory_group_id, None, None, params)
    token = uuid.uuid4()
    assert await claim_job(async_test_db, memory_job_id, token, timedelta(minutes=5)) is not None
    first, second = (chapter.chapter_id for chapter in chapters)

    # A direct naming run waits for recording of every chapter, not just its own.
    record_first = await claim_task(async_test_db, memory_job_id, first, token, StageBarrierSchedule(), stage_num=0)
    assert record_first is not None
    await _complete_task(async_test_db, memory_job_id, first, stage_num=0)
    assert await claim_task(async_test_db, memory_job_id, first, token, StageBarrierSchedule(), stage_num=1) is None

    schedule = StageBarrierSchedule()
    claimed = []
    while (task := await claim_next_task(async_test_db, memory_job_id, token, schedule)) is not None:
        claimed.append((task.chapter_id, task.stage_num))
        # Schedule invariant: the worker never claims a task that direct runs would refuse.
        prerequisites = schedule.unfinished_prerequisites(memory_job_id, task.chapter_id, task.stage_num)
        assert not await async_test_db.scalar(select(prerequisites))
        await _complete_task(async_test_db, memory_job_id, task.chapter_id, task.stage_num)
    assert claimed == [(second, 0), (first, 1), (second, 1)]
