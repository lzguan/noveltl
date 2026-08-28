import asyncio
import uuid
from datetime import timedelta

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.languages.models import Language
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.tasks import tasks as agent_tasks
from src.memory.agent.tasks.jobs import JobParams, claim_job, claim_task, make_job
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


def _make_memory_job(test_db: Session, chapter_count: int = 2) -> tuple[uuid.UUID, list[uuid.UUID]]:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory agent task source")
    test_db.add_all([language, source_work])
    test_db.flush()

    novel = Novel(
        novel_title="Memory agent task novel",
        novel_description=None,
        novel_author=None,
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
        for chapter_num in range(1, chapter_count + 1)
    ]
    test_db.add_all(chapters)
    test_db.flush()
    test_db.add_all(
        ChapterContent(
            chapter_content_text=f"Chapter {chapter.chapter_num} text",
            chapter_content_version=1,
            chapter_id=chapter.chapter_id,
        )
        for chapter in chapters
    )

    memory_group = MemoryGroup(
        memory_group_name="Memory agent task group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add(memory_group)
    test_db.commit()

    memory_job_id = make_job(
        test_db,
        memory_group.memory_group_id,
        None,
        None,
        JobParams(model_name="deepseek:deepseek-chat", plugins=[]),
    )
    return memory_job_id, [chapter.chapter_id for chapter in chapters]


def _claim_once(
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
):
    claimed = False

    def claim(db: Session, claim_token: uuid.UUID) -> MemoryChapterTask | None:
        nonlocal claimed
        if claimed:
            return None
        claimed = True
        if claim_job(db, memory_job_id, claim_token, timedelta(minutes=5)) is None:
            return None
        return claim_task(db, memory_job_id, chapter_id, claim_token)

    return claim


def test_aiterate_tasks_returns_session_independent_task_identity(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    memory_job_id, [chapter_id] = _make_memory_job(test_db, chapter_count=1)

    async def collect_tasks():
        claim_token = uuid.uuid4()
        return [
            task
            async for task in agent_tasks.aiterate_tasks(
                testing_session_local,
                claim_token,
                _claim_once(memory_job_id, chapter_id),
            )
        ]

    assert asyncio.run(collect_tasks()) == [agent_tasks.ClaimedTask(memory_job_id, chapter_id)]


def test_arun_tasks_raises_when_completion_claim_is_lost(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    memory_job_id, [chapter_id] = _make_memory_job(test_db, chapter_count=1)

    async def expire_claim(db: Session, _task: agent_tasks.ClaimedTask) -> str:
        db.execute(
            update(MemoryJob)
            .where(MemoryJob.memory_job_id == memory_job_id)
            .values(claim_expires_at=func.now() - timedelta(seconds=1))
        )
        return "processed"

    async def consume_tasks():
        return [
            result
            async for result in agent_tasks.arun_tasks(
                testing_session_local,
                uuid.uuid4(),
                _claim_once(memory_job_id, chapter_id),
                expire_claim,
            )
        ]

    with pytest.raises(MemoryJobClaimLostException, match=str(chapter_id)):
        asyncio.run(consume_tasks())

    test_db.expire_all()
    task = test_db.get(MemoryChapterTask, (memory_job_id, chapter_id))
    assert task is not None
    assert task.task_status == JobStatus.PROCESSING


def test_arun_tasks_preserves_processing_error_when_failure_claim_is_lost(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    memory_job_id, [chapter_id] = _make_memory_job(test_db, chapter_count=1)

    async def fail_after_expiration(_db: Session, _task: agent_tasks.ClaimedTask) -> None:
        with testing_session_local() as other_db:
            other_db.execute(
                update(MemoryJob)
                .where(MemoryJob.memory_job_id == memory_job_id)
                .values(claim_expires_at=func.now() - timedelta(seconds=1))
            )
            other_db.commit()
        raise RuntimeError("model unavailable")

    async def consume_tasks():
        return [
            result
            async for result in agent_tasks.arun_tasks(
                testing_session_local,
                uuid.uuid4(),
                _claim_once(memory_job_id, chapter_id),
                fail_after_expiration,
            )
        ]

    with pytest.raises(RuntimeError, match="model unavailable"):
        asyncio.run(consume_tasks())

    test_db.expire_all()
    task = test_db.get(MemoryChapterTask, (memory_job_id, chapter_id))
    assert task is not None
    assert task.task_status == JobStatus.PROCESSING


def test_run_all_tasks_completes_tasks_refreshes_and_releases_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_job_id, chapter_ids = _make_memory_job(test_db)
    test_agent = Agent(TestModel(call_tools=[], custom_output_text="recorded"), deps_type=MemAgentDeps)
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _plugins: test_agent)

    async def consume_tasks():
        return [
            result.output
            async for result in agent_tasks.run_all_tasks(
                testing_session_local,
                memory_job_id,
            )
        ]

    assert asyncio.run(consume_tasks()) == ["recorded", "recorded"]

    test_db.expire_all()
    tasks = test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == memory_job_id)).all()
    assert {task.chapter_id for task in tasks} == set(chapter_ids)
    assert all(task.task_status == JobStatus.COMPLETED for task in tasks)

    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.claim_token is None
    assert job.claim_expires_at is None


def test_run_task_only_completes_selected_chapter(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_job_id, chapter_ids = _make_memory_job(test_db)
    selected_chapter_id = chapter_ids[1]
    test_agent = Agent(TestModel(call_tools=[], custom_output_text="recorded"), deps_type=MemAgentDeps)
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _plugins: test_agent)

    result = asyncio.run(agent_tasks.run_task(testing_session_local, memory_job_id, selected_chapter_id))

    assert result is not None
    assert result.output == "recorded"
    test_db.expire_all()
    tasks = test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == memory_job_id)).all()
    statuses = {task.chapter_id: task.task_status for task in tasks}
    assert statuses[selected_chapter_id] == JobStatus.COMPLETED
    assert statuses[chapter_ids[0]] == JobStatus.PENDING

    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.claim_token is None
    assert job.claim_expires_at is None
