import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.memory.agent.service import (
    abort_job,
    create_job,
    delete_job,
    delete_task,
    query_job,
    query_jobs,
    query_task,
    query_tasks,
    retry_task,
    start_job,
    start_task,
)
from src.memory.agent.tasks.jobs import JobParams, claim_job
from src.memory.exceptions import (
    MemoryAgentEnqueueFailedException,
    MemoryChapterTaskStateException,
    MemoryGroupNotFoundException,
    MemoryJobStateException,
)
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from test_support.memory import RecordingMemoryAgentDispatcher
from test_support.test_data.scenarios import DatabaseScenario

PARAMS = JobParams(model_name="deepseek:deepseek-chat", plugins=[])


def _create_group(db: Session, scenario: DatabaseScenario, novel_key: str) -> MemoryGroup:
    group = MemoryGroup(
        memory_group_name=f"{novel_key} memory",
        novel_id=scenario.novels[novel_key].novel_id,
        memory_language="zh",
    )
    db.add(group)
    db.commit()
    return group


def test_create_and_query_job_respect_memory_group_permissions(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "ov")
    owner = novel_permission_scenario.users["owner"]
    viewer = novel_permission_scenario.users["other"]

    with pytest.raises(MemoryGroupNotFoundException):
        create_job(test_db, viewer, group.memory_group_id, None, None, PARAMS)

    job = create_job(test_db, owner, group.memory_group_id, None, None, PARAMS)

    assert query_job(test_db, viewer, job.memory_job_id) == job
    assert query_jobs(test_db, viewer, group.memory_group_id) == [job]
    page = query_tasks(test_db, viewer, job.memory_job_id)
    assert page.count == 1
    assert page.rows[0].chapter_num == 1
    assert page.rows[0].task_status == JobStatus.PENDING


def test_start_and_retry_publish_only_runnable_work(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    dispatcher = RecordingMemoryAgentDispatcher()
    job = create_job(test_db, editor, group.memory_group_id, None, None, PARAMS)

    start_job(test_db, editor, dispatcher, job.memory_job_id)
    start_task(test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert dispatcher.jobs == [job.memory_job_id]
    assert dispatcher.tasks == [(job.memory_job_id, chapter_id)]

    test_db.execute(
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == job.memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
        )
        .values(task_status=JobStatus.FAILED)
    )
    test_db.commit()

    retried = retry_task(test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert retried.task_status == JobStatus.PENDING
    assert dispatcher.tasks == [
        (job.memory_job_id, chapter_id),
        (job.memory_job_id, chapter_id),
    ]
    with pytest.raises(MemoryChapterTaskStateException):
        retry_task(test_db, editor, dispatcher, job.memory_job_id, chapter_id)


def test_retry_restores_failed_status_when_publication_fails(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    job = create_job(test_db, editor, group.memory_group_id, None, None, PARAMS)
    test_db.execute(
        update(MemoryChapterTask)
        .where(MemoryChapterTask.memory_job_id == job.memory_job_id)
        .values(task_status=JobStatus.FAILED)
    )
    test_db.commit()
    dispatcher = RecordingMemoryAgentDispatcher(
        enqueue_error=MemoryAgentEnqueueFailedException("broker unavailable")
    )

    with pytest.raises(MemoryAgentEnqueueFailedException, match="broker unavailable"):
        retry_task(test_db, editor, dispatcher, job.memory_job_id, chapter_id)

    assert query_task(test_db, editor, job.memory_job_id, chapter_id).task_status == JobStatus.FAILED


def test_abort_job_clears_claim_without_changing_tasks(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    job = create_job(test_db, editor, group.memory_group_id, None, None, PARAMS)
    assert claim_job(test_db, job.memory_job_id, uuid.uuid4(), timedelta(minutes=5)) is not None

    aborted = abort_job(test_db, editor, job.memory_job_id)

    assert aborted.claim_expires_at is None
    persisted_job = test_db.get(MemoryJob, job.memory_job_id)
    assert persisted_job is not None
    assert persisted_job.claim_token is None
    assert query_task(test_db, editor, job.memory_job_id, chapter_id).task_status == JobStatus.PENDING


def test_delete_operations_reject_active_work_and_job_delete_cascades_tasks(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    chapter_id = novel_permission_scenario.chapters["owner_editor"].chapter_id
    job = create_job(test_db, editor, group.memory_group_id, None, None, PARAMS)
    claim_token = uuid.uuid4()
    assert claim_job(test_db, job.memory_job_id, claim_token, timedelta(minutes=5)) is not None
    test_db.execute(
        update(MemoryChapterTask)
        .where(MemoryChapterTask.memory_job_id == job.memory_job_id)
        .values(task_status=JobStatus.PROCESSING)
    )
    test_db.commit()

    with pytest.raises(MemoryChapterTaskStateException):
        delete_task(test_db, editor, job.memory_job_id, chapter_id)
    with pytest.raises(MemoryJobStateException):
        delete_job(test_db, editor, job.memory_job_id)

    test_db.execute(
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == job.memory_job_id)
        .values(claim_expires_at=func.now() - timedelta(seconds=1))
    )
    test_db.commit()
    delete_job(test_db, editor, job.memory_job_id)

    assert test_db.get(MemoryJob, job.memory_job_id) is None
    assert test_db.scalars(
        select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == job.memory_job_id)
    ).all() == []


def test_deleting_memory_group_cascades_jobs_and_tasks(
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    job = create_job(test_db, editor, group.memory_group_id, None, None, PARAMS)

    test_db.delete(group)
    test_db.commit()

    assert test_db.get(MemoryJob, job.memory_job_id) is None
    assert test_db.scalars(
        select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == job.memory_job_id)
    ).all() == []
