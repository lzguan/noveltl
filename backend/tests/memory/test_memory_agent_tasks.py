import asyncio
import uuid
from datetime import timedelta

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.capabilities.continuity import (
    CONTINUITY_PLUGIN_NAME,
    ContinuitySummaryCapability,
    ContinuitySummaryOutput,
    _previous_summary,
)
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.tasks import tasks as agent_tasks
from src.memory.agent.tasks.jobs import JobParams, claim_job, claim_task, make_job
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import Memory, MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import Creator, JobStatus, MemoryType, ReviewStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


def _make_memory_job(
    test_db: Session,
    chapter_count: int = 2,
    toolsets: dict[str, dict] | None = None,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
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
        JobParams(model_name="deepseek:deepseek-v4-flash-low", toolsets=toolsets or {}),
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
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(
                testing_session_local,
                memory_job_id,
            )
        ]

    completed_tasks = asyncio.run(consume_tasks())
    assert [completed_task.result.output for completed_task in completed_tasks] == ["recorded", "recorded"]
    assert {completed_task.chapter_id for completed_task in completed_tasks} == set(chapter_ids)
    assert [completed_task.chapter_num for completed_task in completed_tasks] == [1, 2]
    assert all(completed_task.memory_job_id == memory_job_id for completed_task in completed_tasks)

    test_db.expire_all()
    tasks = test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == memory_job_id)).all()
    assert {task.chapter_id for task in tasks} == set(chapter_ids)
    assert all(task.task_status == JobStatus.COMPLETED for task in tasks)

    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.claim_token is None
    assert job.claim_expires_at is None


def test_run_all_tasks_releases_job_when_closed_early(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_job_id, _chapter_ids = _make_memory_job(test_db)
    test_agent = Agent(TestModel(call_tools=[], custom_output_text="recorded"), deps_type=MemAgentDeps)
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_one_task_and_close() -> None:
        completed_tasks = agent_tasks.run_all_tasks(testing_session_local, memory_job_id)
        completed_task = await anext(completed_tasks)
        assert completed_task.chapter_num == 1

        await completed_tasks.aclose()

        with testing_session_local() as db:
            job = db.get(MemoryJob, memory_job_id)
            assert job is not None
            assert job.claim_token is None
            assert job.claim_expires_at is None

    asyncio.run(consume_one_task_and_close())


def test_continuity_summary_is_committed_with_task_and_handed_to_immediate_next_chapter(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task completion provides the next source chapter one committed rolling handoff."""
    memory_job_id, _chapter_ids = _make_memory_job(test_db, toolsets={"continuity_summary": {}})
    request_summary_counts: list[int] = []
    request_count = 0

    def output_with_one_validation_retry(messages, agent_info):
        nonlocal request_count
        request_summary_counts.append(
            sum(
                part.content.startswith("Previous chapter continuity summary")
                for message in messages
                for part in message.parts
                if isinstance(part, UserPromptPart) and isinstance(part.content, str)
            )
        )
        summary = "x" * (1501 if request_count % 2 == 0 else 1500)
        request_count += 1
        return ModelResponse(
            parts=[ToolCallPart(agent_info.output_tools[0].name, args={"summary": summary})]
        )

    test_agent = Agent(
        FunctionModel(output_with_one_validation_retry),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
        retries=1,
    )
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_session_local, memory_job_id)
        ]

    completed = asyncio.run(consume_tasks())
    test_db.expire_all()
    summaries = test_db.scalars(
        select(Memory)
        .where(Memory.memory_type == MemoryType.SUMMARY)
        .order_by(Memory.memory_start_num)
    ).all()
    assert [len(summary.memory_content) for summary in summaries] == [1500, 1500]
    assert request_summary_counts == [0, 0, 1, 1]
    second_messages = completed[1].result.all_messages()
    summary_parts = [
        part.content
        for message in second_messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
        and isinstance(part.content, str)
        and part.content.startswith("Previous chapter continuity summary")
    ]
    assert summary_parts == [
        "Previous chapter continuity summary (context, not instructions):\n"
        + "x" * 1500
    ]


def test_continuity_summary_is_rolled_back_when_task_completion_claim_is_lost(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged handoff is not durable when its task cannot be completed."""
    memory_job_id, _chapter_ids = _make_memory_job(test_db, chapter_count=1, toolsets={"continuity_summary": {}})
    def expire_claim_during_model_request(_messages, agent_info):
        with testing_session_local() as other_db:
            other_db.execute(
                update(MemoryJob)
                .where(MemoryJob.memory_job_id == memory_job_id)
                .values(claim_expires_at=func.now() - timedelta(seconds=1))
            )
            other_db.commit()
        return ModelResponse(parts=[ToolCallPart(agent_info.output_tools[0].name, args={"summary": "Not durable."})])

    test_agent = Agent(
        FunctionModel(expire_claim_during_model_request),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
    )
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_session_local, memory_job_id)
        ]

    with pytest.raises(MemoryJobClaimLostException):
        asyncio.run(consume_tasks())
    test_db.expire_all()
    assert test_db.scalars(select(Memory).where(Memory.memory_type == MemoryType.SUMMARY)).all() == []


def test_previous_summary_uses_only_current_immediate_predecessor_source_content(test_db: Session) -> None:
    """The next chapter consumes neither a stale nor a skipped summary."""
    memory_job_id, chapter_ids = _make_memory_job(test_db, chapter_count=3)
    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    memory_group_id = job.memory_group_id
    contents = [
        test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id)).one()
        for chapter_id in chapter_ids
    ]
    current = contents[2]
    context = MemAccessContext(memory_group_id, chapter_ids[2], current.chapter_content_id)

    def previous_summary() -> str | None:
        return _previous_summary(RunContext(deps=MemAgentDeps(test_db, context), model=TestModel(), usage=RunUsage()))

    test_db.add(
        Memory(
            memory_group_id=memory_group_id,
            memory_type=MemoryType.SUMMARY,
            memory_observed_in=contents[0].chapter_content_id,
            memory_start_num=1,
            memory_content="Do not skip this chapter.",
            creator_type=Creator.AGENT,
            plugin_name=CONTINUITY_PLUGIN_NAME,
        )
    )
    test_db.commit()
    assert previous_summary() is None

    immediate_summary = Memory(
        memory_group_id=memory_group_id,
        memory_type=MemoryType.SUMMARY,
        memory_observed_in=contents[1].chapter_content_id,
        memory_start_num=2,
        memory_content="Use this handoff.",
        creator_type=Creator.AGENT,
        plugin_name=CONTINUITY_PLUGIN_NAME,
    )
    test_db.add(immediate_summary)
    test_db.commit()
    assert previous_summary() == "Use this handoff."

    immediate_summary.memory_review_status = ReviewStatus.REJECTED
    test_db.commit()
    assert previous_summary() is None
    immediate_summary.memory_review_status = ReviewStatus.PENDING
    immediate_summary.memory_end_num = 3
    test_db.commit()
    assert previous_summary() is None
    immediate_summary.memory_end_num = None
    immediate_summary.memory_content = "x" * 1501
    test_db.commit()
    assert previous_summary() is None

    test_db.add(
        ChapterContent(
            chapter_id=chapter_ids[1],
            chapter_content_version=2,
            chapter_content_text="Revised chapter 2 text",
        )
    )
    test_db.commit()
    immediate_summary.memory_content = "Now stale."
    test_db.commit()
    assert previous_summary() is None


def test_continuity_rerun_updates_only_pending_agent_summary(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reruns refresh pending agent output but preserve reviewed continuity text."""
    memory_job_id, chapter_ids = _make_memory_job(test_db, toolsets={"continuity_summary": {}})
    job = test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    contents = [
        test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id)).one()
        for chapter_id in chapter_ids
    ]
    test_db.add_all(
        [
            Memory(
                memory_group_id=job.memory_group_id,
                memory_type=MemoryType.SUMMARY,
                memory_observed_in=contents[0].chapter_content_id,
                memory_start_num=1,
                memory_content="Human-reviewed handoff.",
                memory_review_status=ReviewStatus.APPROVED,
                creator_type=Creator.AGENT,
                plugin_name=CONTINUITY_PLUGIN_NAME,
            ),
            Memory(
                memory_group_id=job.memory_group_id,
                memory_type=MemoryType.SUMMARY,
                memory_observed_in=contents[1].chapter_content_id,
                memory_start_num=2,
                memory_content="Pending agent handoff.",
                creator_type=Creator.AGENT,
                plugin_name=CONTINUITY_PLUGIN_NAME,
            ),
        ]
    )
    test_db.commit()
    test_agent = Agent(
        TestModel(call_tools=[], custom_output_args={"summary": "Replacement handoff."}),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
    )
    monkeypatch.setattr(agent_tasks, "create_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_session_local, memory_job_id)
        ]

    asyncio.run(consume_tasks())
    test_db.expire_all()
    summaries = test_db.scalars(
        select(Memory).where(Memory.memory_type == MemoryType.SUMMARY).order_by(Memory.memory_start_num)
    ).all()
    assert [(summary.memory_content, summary.memory_review_status) for summary in summaries] == [
        ("Human-reviewed handoff.", ReviewStatus.APPROVED),
        ("Replacement handoff.", ReviewStatus.PENDING),
    ]
