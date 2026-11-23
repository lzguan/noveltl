import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.memory.agent.config import JobParamsV1 as JobParams
from src.memory.agent.config import (
    JobParamsV2,
    JobParamsV3,
    RecordMemoriesConfig,
    TranslateTermsConfig,
    TranslateTermsStageConfig,
)
from src.memory.agent.service import (
    create_job,
    delete_job,
    delete_task,
    query_job,
    query_job_summaries,
    query_job_summary,
    query_jobs,
    query_task,
    query_tasks,
    retry_task,
    start_job,
    start_task,
)
from src.memory.agent.tasks.jobs import claim_job
from src.memory.exceptions import (
    MemoryAgentEnqueueFailedException,
    MemoryChapterTaskStateException,
    MemoryGroupNotFoundException,
    MemoryJobStateException,
)
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from src.novels.models import Chapter
from test_support.memory import RecordingMemoryAgentDispatcher
from test_support.test_data.scenarios import DatabaseScenario

PARAMS = JobParams(model_name="deepseek:deepseek-v4-flash-low", toolsets={})


def _create_group(db: Session, scenario: DatabaseScenario, novel_key: str) -> MemoryGroup:
    group = MemoryGroup(
        memory_group_name=f"{novel_key} memory",
        novel_id=scenario.novels[novel_key].novel_id,
        memory_language="zh",
    )
    db.add(group)
    db.commit()
    return group


@pytest.mark.parametrize(
    "params",
    [
        PARAMS,
        JobParamsV2(translate_terms=TranslateTermsConfig(model_name="deepseek:deepseek-v4-flash-low")),
    ],
)
async def test_create_and_query_job_respect_memory_group_permissions(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
    params: JobParams | JobParamsV2,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "ov")
    owner = novel_permission_scenario.users["owner"]
    viewer = novel_permission_scenario.users["other"]

    with pytest.raises(MemoryGroupNotFoundException):
        await create_job(async_test_db, viewer, group.memory_group_id, None, None, params)

    job = await create_job(async_test_db, owner, group.memory_group_id, None, None, params)

    assert await query_job(async_test_db, viewer, job.memory_job_id) == job
    assert await query_jobs(async_test_db, viewer, group.memory_group_id) == [job]
    summary = (await query_job_summary(async_test_db, viewer, job.memory_job_id)).summary
    assert summary.job == job
    assert summary.task_counts.pending == 1
    assert summary.task_counts.processing == 0
    assert summary.task_counts.completed == 0
    assert summary.task_counts.failed == 0
    assert (await query_job_summaries(async_test_db, viewer, group.memory_group_id)).summaries == [summary]
    page = await query_tasks(async_test_db, viewer, job.memory_job_id)
    assert page.count == 1
    assert page.rows[0].chapter_num == 1
    assert page.rows[0].task_status == JobStatus.PENDING
    task = page.rows[0]
    assert await query_task(async_test_db, viewer, job.memory_job_id, task.chapter_id) == task
    assert (
        await start_task(async_test_db, owner, RecordingMemoryAgentDispatcher(), job.memory_job_id, task.chapter_id)
        == task
    )

    test_db.execute(
        update(MemoryChapterTask)
        .where(MemoryChapterTask.memory_job_id == job.memory_job_id)
        .values(task_status=JobStatus.FAILED)
    )
    test_db.commit()
    failed_summary = (await query_job_summary(async_test_db, viewer, job.memory_job_id)).summary
    assert failed_summary.task_counts.pending == 0
    assert failed_summary.task_counts.failed == 1


async def test_tasks_are_listed_in_the_order_the_schedule_runs_them(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "ov")
    owner = novel_permission_scenario.users["owner"]
    first = novel_permission_scenario.chapters["owner_viewer"]
    second = Chapter(
        chapter_num=first.chapter_num + 1,
        chapter_title="Second",
        chapter_is_public=False,
        novel_id=first.novel_id,
    )
    test_db.add(second)
    test_db.commit()
    params = JobParamsV2(
        record_memories=RecordMemoriesConfig(model_name="deepseek:deepseek-v4-flash-low", toolsets={}),
        translate_terms=TranslateTermsConfig(model_name="deepseek:deepseek-v4-flash-low"),
    )
    job = await create_job(async_test_db, owner, group.memory_group_id, None, None, params)

    rows = (await query_tasks(async_test_db, owner, job.memory_job_id)).rows

    # Stage barriers: every recording task runs before any naming task.
    assert [(row.stage_num, row.chapter_id) for row in rows] == [
        (0, first.chapter_id),
        (0, second.chapter_id),
        (1, first.chapter_id),
        (1, second.chapter_id),
    ]


async def test_jobs_are_stored_as_written_and_returned_as_v3(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "ov")
    owner = novel_permission_scenario.users["owner"]
    params = JobParamsV2(translate_terms=TranslateTermsConfig(model_name="deepseek:deepseek-v4-flash-low"))

    job = await create_job(async_test_db, owner, group.memory_group_id, None, None, params)

    stored = test_db.get(MemoryJob, job.memory_job_id)
    assert stored is not None and stored.job_params == params.model_dump(mode="json")
    assert job.job_params == JobParamsV3(
        stages=[TranslateTermsStageConfig(model_name="deepseek:deepseek-v4-flash-low")]
    )


async def test_start_and_retry_publish_only_runnable_work(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    dispatcher = RecordingMemoryAgentDispatcher()
    job = await create_job(async_test_db, editor, group.memory_group_id, None, None, PARAMS)

    await start_job(async_test_db, editor, dispatcher, job.memory_job_id)
    await start_task(async_test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert dispatcher.jobs == [job.memory_job_id]
    assert dispatcher.tasks == [(job.memory_job_id, chapter_id, 0)]

    test_db.execute(
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == job.memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
        )
        .values(task_status=JobStatus.FAILED)
    )
    test_db.commit()

    retried = await retry_task(async_test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert retried.task_status == JobStatus.PENDING
    assert dispatcher.tasks == [
        (job.memory_job_id, chapter_id, 0),
        (job.memory_job_id, chapter_id, 0),
    ]
    with pytest.raises(MemoryChapterTaskStateException):
        await retry_task(async_test_db, editor, dispatcher, job.memory_job_id, chapter_id)


async def test_retry_restores_failed_status_when_publication_fails(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    job = await create_job(async_test_db, editor, group.memory_group_id, None, None, PARAMS)
    test_db.execute(
        update(MemoryChapterTask)
        .where(MemoryChapterTask.memory_job_id == job.memory_job_id)
        .values(task_status=JobStatus.FAILED)
    )
    test_db.commit()
    dispatcher = RecordingMemoryAgentDispatcher(enqueue_error=MemoryAgentEnqueueFailedException("broker unavailable"))

    with pytest.raises(MemoryAgentEnqueueFailedException, match="broker unavailable"):
        await retry_task(async_test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert (await query_task(async_test_db, editor, job.memory_job_id, chapter_id)).task_status == JobStatus.FAILED


async def test_delete_operations_reject_active_work_and_job_delete_cascades_tasks(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    job = await create_job(async_test_db, editor, group.memory_group_id, None, None, PARAMS)
    claim_token = uuid.uuid4()
    assert claim_job(test_db, job.memory_job_id, claim_token, timedelta(minutes=5)) is not None
    test_db.execute(
        update(MemoryChapterTask)
        .where(MemoryChapterTask.memory_job_id == job.memory_job_id)
        .values(task_status=JobStatus.PROCESSING)
    )
    test_db.commit()

    with pytest.raises(MemoryChapterTaskStateException):
        await delete_task(async_test_db, editor, job.memory_job_id, chapter_id)
    with pytest.raises(MemoryJobStateException):
        await delete_job(async_test_db, editor, job.memory_job_id)

    test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == job.memory_job_id)
        .values(claim_expires_at=func.now() - timedelta(seconds=1))
    )
    test_db.commit()
    await delete_job(async_test_db, editor, job.memory_job_id)

    assert test_db.get(MemoryJob, job.memory_job_id) is None
    assert (
        test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == job.memory_job_id)).all()
        == []
    )


async def test_deleting_memory_group_cascades_jobs_and_tasks(
    test_db: Session,
    async_test_db: AsyncSession,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    job = await create_job(async_test_db, editor, group.memory_group_id, None, None, PARAMS)

    test_db.delete(group)
    test_db.commit()

    assert test_db.get(MemoryJob, job.memory_job_id) is None
    assert (
        test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == job.memory_job_id)).all()
        == []
    )
