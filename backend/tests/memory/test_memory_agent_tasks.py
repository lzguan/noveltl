import uuid
from datetime import timedelta

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import Toolset
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.languages.models import Language
from src.memory.access import CONTINUITY_PLUGIN_NAME, MemAccessContext, read_previous_continuity_summary
from src.memory.agent.capabilities.continuity import (
    ContinuitySummaryCapability,
    ContinuitySummaryOutput,
)
from src.memory.agent.config import JobParamsV1 as JobParams
from src.memory.agent.config import JobParamsV2
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.stages import recording
from src.memory.agent.tasks import tasks as agent_tasks
from src.memory.agent.tasks.jobs import claim_job, claim_task, make_job
from src.memory.agent.tasks.schedule import StageBarrierSchedule
from src.memory.agent.toolsets.glossary.definitions import glossary_definitions_write_toolset
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import Memory, MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import MemoryWorkspace, ShadowTerm
from src.memory.types import Creator, JobStatus, MemoryType, ReviewStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


async def _make_memory_job(
    async_test_db: AsyncSession,
    chapter_count: int = 2,
    toolsets: dict[str, dict] | None = None,
    params: JobParams | JobParamsV2 | None = None,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory agent task source")
    async_test_db.add_all([language, source_work])
    await async_test_db.flush()

    novel = Novel(
        novel_title="Memory agent task novel",
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
        Chapter(
            chapter_num=chapter_num,
            chapter_title=f"Chapter {chapter_num}",
            chapter_is_public=False,
            novel_id=novel.novel_id,
        )
        for chapter_num in range(1, chapter_count + 1)
    ]
    async_test_db.add_all(chapters)
    await async_test_db.flush()
    async_test_db.add_all(
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
    async_test_db.add(memory_group)
    await async_test_db.commit()

    memory_job_id = await make_job(
        async_test_db,
        memory_group.memory_group_id,
        None,
        None,
        params or JobParams(model_name="deepseek:deepseek-v4-flash-low", toolsets=toolsets or {}),
    )
    return memory_job_id, [chapter.chapter_id for chapter in chapters]


def _claim_once(
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
):
    claimed = False

    async def claim(db: AsyncSession, claim_token: uuid.UUID) -> MemoryChapterTask | None:
        nonlocal claimed
        if claimed:
            return None
        claimed = True
        if await claim_job(db, memory_job_id, claim_token, timedelta(minutes=5)) is None:
            return None
        return await claim_task(db, memory_job_id, chapter_id, claim_token, StageBarrierSchedule())

    return claim


async def test_arun_tasks_preserves_processing_error_when_failure_claim_is_lost(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
) -> None:
    memory_job_id, [chapter_id] = await _make_memory_job(async_test_db, chapter_count=1)

    async def fail_after_expiration(
        _db: AsyncSession, _task: agent_tasks.ClaimedTask
    ) -> agent_tasks.CompletedMemoryTask:
        async with testing_async_session_local() as other_db:
            await other_db.execute(
                update(MemoryJob)
                .where(MemoryJob.memory_job_id == memory_job_id)
                .values(claim_expires_at=func.now() - timedelta(seconds=1))
            )
            await other_db.commit()
        raise RuntimeError("model unavailable")

    async def consume_tasks():
        return [
            result
            async for result in agent_tasks.arun_tasks(
                testing_async_session_local,
                uuid.uuid4(),
                _claim_once(memory_job_id, chapter_id),
                fail_after_expiration,
            )
        ]

    with pytest.raises(RuntimeError, match="model unavailable"):
        (await consume_tasks())

    async_test_db.expunge_all()
    task = await async_test_db.get(MemoryChapterTask, (memory_job_id, chapter_id, 0))
    assert task is not None
    assert task.task_status == JobStatus.PROCESSING


async def test_conventions_stage_creates_one_task_on_the_last_chapter(async_test_db: AsyncSession) -> None:
    """The range-wide stage sits between per-chapter stages, so barriers order it after all recording."""
    from src.memory.agent.config import RecordMemoriesConfig, SummarizeConventionsConfig, TranslateTermsConfig

    model = "deepseek:deepseek-v4-flash-low"
    job_id, chapter_ids = await _make_memory_job(
        async_test_db,
        chapter_count=3,
        params=JobParamsV2(
            record_memories=RecordMemoriesConfig(model_name=model, toolsets={}),
            summarize_conventions=SummarizeConventionsConfig(model_name=model),
            translate_terms=TranslateTermsConfig(model_name=model),
        ),
    )

    tasks = (
        await async_test_db.execute(
            select(MemoryChapterTask.stage_num, MemoryChapterTask.chapter_id).where(
                MemoryChapterTask.memory_job_id == job_id
            )
        )
    ).all()
    chapters_by_stage: dict[int, set[uuid.UUID]] = {}
    for stage_num, chapter_id in tasks:
        chapters_by_stage.setdefault(stage_num, set()).add(chapter_id)
    assert chapters_by_stage == {0: set(chapter_ids), 1: {chapter_ids[-1]}, 2: set(chapter_ids)}


async def test_run_all_tasks_completes_tasks_refreshes_and_releases_job(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_job_id, chapter_ids = await _make_memory_job(async_test_db)
    test_agent = Agent(TestModel(call_tools=[], custom_output_text="recorded"), deps_type=MemAgentDeps)
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(
                testing_async_session_local,
                memory_job_id,
            )
        ]

    completed_at_renewal = []
    engine = async_test_db.get_bind().engine

    def observe_claim_update(_conn, _cursor, statement, _parameters, _context, _many):
        set_clause = statement.split(" WHERE ")[0]
        if (
            statement.startswith("UPDATE memory_jobs SET")
            and "claim_expires_at" in set_clause
            and "claim_token" not in set_clause
        ):
            with testing_session_local() as other:
                completed_at_renewal.append(
                    other.scalar(
                        select(func.count())
                        .select_from(MemoryChapterTask)
                        .where(
                            MemoryChapterTask.memory_job_id == memory_job_id,
                            MemoryChapterTask.task_status == JobStatus.COMPLETED,
                        )
                    )
                )

    event.listen(engine, "before_cursor_execute", observe_claim_update)
    try:
        completed_tasks = await consume_tasks()
    finally:
        event.remove(engine, "before_cursor_execute", observe_claim_update)
    assert completed_at_renewal == [1, 2]
    assert all(completed_task.result is not None for completed_task in completed_tasks)
    assert [
        completed_task.result.output for completed_task in completed_tasks if completed_task.result is not None
    ] == ["recorded", "recorded"]
    assert {completed_task.chapter_id for completed_task in completed_tasks} == set(chapter_ids)
    assert [completed_task.chapter_num for completed_task in completed_tasks] == [1, 2]
    assert all(completed_task.memory_job_id == memory_job_id for completed_task in completed_tasks)

    async_test_db.expunge_all()
    tasks = (
        await async_test_db.scalars(select(MemoryChapterTask).where(MemoryChapterTask.memory_job_id == memory_job_id))
    ).all()
    assert {task.chapter_id for task in tasks} == set(chapter_ids)
    assert all(task.task_status == JobStatus.COMPLETED for task in tasks)

    job = await async_test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    assert job.claim_token is None
    assert job.claim_expires_at is None


async def test_run_all_tasks_releases_job_when_closed_early(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_job_id, _chapter_ids = await _make_memory_job(async_test_db)
    test_agent = Agent(TestModel(call_tools=[], custom_output_text="recorded"), deps_type=MemAgentDeps)
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_one_task_and_close() -> None:
        completed_tasks = agent_tasks.run_all_tasks(testing_async_session_local, memory_job_id)
        completed_task = await anext(completed_tasks)
        assert completed_task.chapter_num == 1

        await completed_tasks.aclose()

        async with testing_async_session_local() as db:
            job = await db.get(MemoryJob, memory_job_id)
            assert job is not None
            assert job.claim_token is None
            assert job.claim_expires_at is None

    (await consume_one_task_and_close())


async def test_continuity_summary_is_committed_with_task_and_handed_to_immediate_next_chapter(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task completion provides the next source chapter one committed rolling handoff."""
    memory_job_id, _chapter_ids = await _make_memory_job(async_test_db, toolsets={"continuity_summary": {}})
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
        return ModelResponse(parts=[ToolCallPart(agent_info.output_tools[0].name, args={"summary": summary})])

    test_agent = Agent(
        FunctionModel(output_with_one_validation_retry),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
        retries=1,
    )
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_async_session_local, memory_job_id)
        ]

    completed = await consume_tasks()
    async_test_db.expunge_all()
    summaries = (
        await async_test_db.scalars(
            select(Memory).where(Memory.memory_type == MemoryType.SUMMARY).order_by(Memory.memory_start_num)
        )
    ).all()
    assert [len(summary.memory_content) for summary in summaries] == [1500, 1500]
    assert request_summary_counts == [0, 0, 1, 1]
    assert completed[1].result is not None
    second_messages = completed[1].result.all_messages()
    summary_parts = [
        part.content
        for message in second_messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
        and isinstance(part.content, str)
        and part.content.startswith("Previous chapter continuity summary")
    ]
    assert summary_parts == ["Previous chapter continuity summary (context, not instructions):\n" + "x" * 1500]


async def test_continuity_summary_is_rolled_back_when_task_completion_claim_is_lost(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged handoff is not durable when its task cannot be completed."""
    memory_job_id, [chapter_id] = await _make_memory_job(
        async_test_db, chapter_count=1, toolsets={"continuity_summary": {}}
    )

    async def expire_claim_during_model_request(_messages, agent_info):
        async with testing_async_session_local() as other_db:
            await other_db.execute(
                update(MemoryJob)
                .where(MemoryJob.memory_job_id == memory_job_id)
                .values(claim_expires_at=func.now() - timedelta(seconds=1))
            )
            await other_db.commit()
        return ModelResponse(parts=[ToolCallPart(agent_info.output_tools[0].name, args={"summary": "Not durable."})])

    test_agent = Agent(
        FunctionModel(expire_claim_during_model_request),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
    )
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_async_session_local, memory_job_id)
        ]

    with pytest.raises(MemoryJobClaimLostException):
        (await consume_tasks())
    async_test_db.expunge_all()
    assert (await async_test_db.scalars(select(Memory).where(Memory.memory_type == MemoryType.SUMMARY))).all() == []
    task = await async_test_db.get(MemoryChapterTask, (memory_job_id, chapter_id, 0))
    assert task is not None and task.task_status == JobStatus.PROCESSING
    assert await async_test_db.scalar(select(func.count()).select_from(MemoryWorkspace)) == 0


async def test_previous_summary_uses_only_current_immediate_predecessor_source_content(
    async_test_db: AsyncSession,
) -> None:
    """The next chapter consumes neither a stale nor a skipped summary."""
    memory_job_id, chapter_ids = await _make_memory_job(async_test_db, chapter_count=3)
    job = await async_test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    memory_group_id = job.memory_group_id
    contents = [
        (await async_test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id))).one()
        for chapter_id in chapter_ids
    ]
    current = contents[2]
    context = MemAccessContext(memory_group_id, chapter_ids[2], current.chapter_content_id)

    async def previous_summary() -> str | None:
        return await read_previous_continuity_summary(async_test_db, context)

    async_test_db.add(
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
    await async_test_db.commit()
    assert await previous_summary() is None

    immediate_summary = Memory(
        memory_group_id=memory_group_id,
        memory_type=MemoryType.SUMMARY,
        memory_observed_in=contents[1].chapter_content_id,
        memory_start_num=2,
        memory_content="Use this handoff.",
        creator_type=Creator.AGENT,
        plugin_name=CONTINUITY_PLUGIN_NAME,
    )
    async_test_db.add(immediate_summary)
    await async_test_db.commit()
    assert await previous_summary() == "Use this handoff."

    immediate_summary.memory_review_status = ReviewStatus.REJECTED
    await async_test_db.commit()
    assert await previous_summary() is None
    immediate_summary.memory_review_status = ReviewStatus.PENDING
    immediate_summary.memory_end_num = 3
    await async_test_db.commit()
    assert await previous_summary() is None
    immediate_summary.memory_end_num = None
    immediate_summary.memory_content = "x" * 1501
    await async_test_db.commit()
    assert await previous_summary() is None

    async_test_db.add(
        ChapterContent(
            chapter_id=chapter_ids[1],
            chapter_content_version=2,
            chapter_content_text="Revised chapter 2 text",
        )
    )
    await async_test_db.commit()
    immediate_summary.memory_content = "Now stale."
    await async_test_db.commit()
    assert await previous_summary() is None


async def test_continuity_rerun_updates_only_pending_agent_summary(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reruns refresh pending agent output but preserve reviewed continuity text."""
    memory_job_id, chapter_ids = await _make_memory_job(async_test_db, toolsets={"continuity_summary": {}})
    job = await async_test_db.get(MemoryJob, memory_job_id)
    assert job is not None
    contents = [
        (await async_test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id))).one()
        for chapter_id in chapter_ids
    ]
    async_test_db.add_all(
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
    await async_test_db.commit()
    test_agent = Agent(
        TestModel(call_tools=[], custom_output_args={"summary": "Replacement handoff."}),
        deps_type=MemAgentDeps,
        output_type=ContinuitySummaryOutput,
        capabilities=[ContinuitySummaryCapability()],
    )
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: test_agent)

    async def consume_tasks():
        return [
            completed_task
            async for completed_task in agent_tasks.run_all_tasks(testing_async_session_local, memory_job_id)
        ]

    (await consume_tasks())
    async_test_db.expunge_all()
    summaries = (
        await async_test_db.scalars(
            select(Memory).where(Memory.memory_type == MemoryType.SUMMARY).order_by(Memory.memory_start_num)
        )
    ).all()
    assert [(summary.memory_content, summary.memory_review_status) for summary in summaries] == [
        ("Human-reviewed handoff.", ReviewStatus.APPROVED),
        ("Replacement handoff.", ReviewStatus.PENDING),
    ]


async def test_naming_failure_preserves_recording_and_retry_runs_only_naming(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user can retry naming without paying for or rolling back successful recording.

    FunctionModel replaces paid, nondeterministic provider inference. All task
    claims, glossary writes, stage boundaries, and transactions use PostgreSQL.
    """
    from src.memory.agent.agents import term_translation as naming_agent_factory
    from src.memory.agent.config import RecordMemoriesConfig, TranslateTermsConfig
    from src.memory.agent.tasks.jobs import reset_failed_task
    from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
    from src.memory.plugins.glossary.models import GlossaryTerm

    job_id, [chapter_id] = await _make_memory_job(
        async_test_db,
        chapter_count=1,
        params=JobParamsV2(
            record_memories=RecordMemoriesConfig(
                model_name="deepseek:deepseek-v4-flash-low", toolsets={"glossary_terms": {}}
            ),
            translate_terms=TranslateTermsConfig(model_name="deepseek:deepseek-v4-flash-low"),
        ),
    )
    content = (await async_test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id))).one()
    content.chapter_content_text = "林昀 entered the room."
    await async_test_db.commit()
    recording_calls = 0

    def record(messages, info):
        nonlocal recording_calls
        recording_calls += 1
        if recording_calls == 1:
            return ModelResponse(parts=[ToolCallPart("add_term", {"term_name": "林昀", "term_kind": "person"})])
        from pydantic_ai.messages import TextPart

        return ModelResponse(parts=[TextPart("Recorded.")])

    recording_agent = Agent(FunctionModel(record), deps_type=MemAgentDeps, toolsets=[glossary_term_toolset])
    monkeypatch.setattr(recording, "create_recording_agent", lambda *_: recording_agent)
    fail_naming = True
    naming_requests = 0

    def name(_messages, info):
        nonlocal naming_requests
        if fail_naming:
            raise RuntimeError("Provider unavailable")
        naming_requests += 1
        if naming_requests == 1:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"translations": []})])
        return ModelResponse(
            parts=[
                ToolCallPart(info.output_tools[0].name, {"translations": [{"term": "林昀", "translation": "Lin Yun"}]})
            ]
        )

    monkeypatch.setattr(naming_agent_factory, "model_configuration", lambda _: (FunctionModel(name), {}))

    async def consume():
        return [item async for item in agent_tasks.run_all_tasks(testing_async_session_local, job_id)]

    with pytest.raises(RuntimeError, match="Provider unavailable"):
        (await consume())
    async_test_db.expunge_all()
    record_task = await async_test_db.get(MemoryChapterTask, (job_id, chapter_id, 0))
    naming_task = await async_test_db.get(MemoryChapterTask, (job_id, chapter_id, 1))
    assert record_task is not None and record_task.task_status == JobStatus.COMPLETED
    assert naming_task is not None and naming_task.task_status == JobStatus.FAILED
    assert await async_test_db.scalar(select(GlossaryTerm.term).where(GlossaryTerm.term == "林昀")) == "林昀"
    assert await async_test_db.scalar(select(TermTranslation)) is None
    calls_after_recording = recording_calls

    # Starting again must not skip a failed stage and silently advance.
    assert (await consume()) == []
    assert await reset_failed_task(async_test_db, job_id, chapter_id, 1)
    fail_naming = False
    completed = await agent_tasks.run_one_task(testing_async_session_local, job_id, chapter_id, 1)
    assert completed is not None and completed.stage_name == "translate_terms"
    assert naming_requests == 2  # The typed output validator retries the incomplete response.
    assert recording_calls == calls_after_recording
    async_test_db.expunge_all()
    record_task = await async_test_db.get(MemoryChapterTask, (job_id, chapter_id, 0))
    naming_task = await async_test_db.get(MemoryChapterTask, (job_id, chapter_id, 1))
    assert record_task is not None and record_task.attempt_count == 1
    assert naming_task is not None and naming_task.attempt_count == 2
    translation = (await async_test_db.scalars(select(TermTranslation))).one()
    assert translation.translation == "Lin Yun"
    assert translation.review_status == ReviewStatus.PENDING


async def test_naming_only_no_work_completes_without_creating_an_agent(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.memory.agent.config import TranslateTermsConfig
    from src.memory.agent.stages import term_translation
    from src.memory.plugins.glossary import access

    job_id, [chapter_id] = await _make_memory_job(
        async_test_db,
        chapter_count=1,
        params=JobParamsV2(translate_terms=TranslateTermsConfig(model_name="deepseek:deepseek-v4-flash-low")),
    )
    job = await async_test_db.get(MemoryJob, job_id)
    assert job is not None
    content = (await async_test_db.scalars(select(ChapterContent).where(ChapterContent.chapter_id == chapter_id))).one()
    content.chapter_content_text = "林昀 entered the room."
    term = await access.create_term(async_test_db, job.memory_group_id, "林昀")
    async_test_db.add(
        TermTranslation(
            term_id=term.term_id, translation="Lin Yun", creator_type=Creator.USER, review_status=ReviewStatus.APPROVED
        )
    )
    await async_test_db.commit()

    def unexpected_agent(*_):
        raise AssertionError("No-work naming must not create or run an agent")

    monkeypatch.setattr(term_translation, "create_term_translation_agent", unexpected_agent)
    completed = await agent_tasks.run_one_task(testing_async_session_local, job_id, chapter_id)
    assert completed is not None and completed.result is None
    assert completed.stage_num == 0 and completed.stage_name == "translate_terms"
    async_test_db.expunge_all()
    task = await async_test_db.get(MemoryChapterTask, (job_id, chapter_id, 0))
    assert task is not None and task.task_status == JobStatus.COMPLETED
    assert (await async_test_db.scalars(select(TermTranslation))).one().translation == "Lin Yun"


@pytest.mark.parametrize("fail", [False, True])
async def test_worker_publishes_success_and_discards_drafts_on_model_failure(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    memory_job_id, [chapter_id] = await _make_memory_job(
        async_test_db, chapter_count=1, toolsets={"glossary_terms": {}}
    )
    requests = 0

    async def respond(_messages, _info):
        nonlocal requests
        requests += 1
        async with testing_async_session_local() as other:
            assert await other.scalar(select(func.count()).select_from(GlossaryTerm)) == 0
            if requests > 1:
                assert await other.scalar(select(func.count()).select_from(ShadowTerm)) == 1
        if requests == 1:
            return ModelResponse(parts=[ToolCallPart("add_term", {"term_name": "Alpha", "term_kind": "concept"})])
        if fail:
            raise RuntimeError("Model request failed")
        if requests == 2:
            return ModelResponse(
                parts=[ToolCallPart("new_definition_memory", {"term_names": ["Alpha"], "content": "A concept."})]
            )
        return ModelResponse(parts=[TextPart("Done.")])

    agent = Agent(
        FunctionModel(respond),
        deps_type=MemAgentDeps,
        capabilities=[Toolset(glossary_term_toolset), Toolset(glossary_definitions_write_toolset)],
    )
    monkeypatch.setattr(recording, "create_recording_agent", lambda _model_name, _toolsets: agent)

    async def consume():
        return [item async for item in agent_tasks.run_all_tasks(testing_async_session_local, memory_job_id)]

    if fail:
        with pytest.raises(RuntimeError, match="Model request failed"):
            (await consume())
    else:
        assert len(await consume()) == 1
    async_test_db.expunge_all()
    task = await async_test_db.get(MemoryChapterTask, (memory_job_id, chapter_id, 0))
    assert task is not None and task.task_status == (JobStatus.FAILED if fail else JobStatus.COMPLETED)
    assert await async_test_db.scalar(select(func.count()).select_from(GlossaryTerm)) == (0 if fail else 1)
    assert await async_test_db.scalar(select(func.count()).select_from(Memory)) == (0 if fail else 1)
    assert await async_test_db.scalar(select(func.count()).select_from(MemoryWorkspace)) == 0
