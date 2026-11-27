from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.novels.models import Chapter, ChapterContent
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, ConventionsRecord, MemoriesRecord, TermsRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.task_names import LOAD_INPUTS_LOAD
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.steps import run_step, step_task
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore


async def _group(db: AsyncSession, scenario: DatabaseScenario) -> MemoryGroup:
    novel = scenario.novels["novel_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Inputs", memory_language=novel.language_code)
    db.add(group)
    await db.flush()
    db.add(
        Memory(
            memory_group_id=group.memory_group_id,
            memory_observed_in=scenario.contents["chapter_1_v2"].chapter_content_id,
            memory_type=MemoryType.FACT,
            memory_content="Original candidate",
            memory_start_num=0,
            creator_type=Creator.USER,
            plugin_name="continuity",
        )
    )
    await db.flush()
    return group


def _request(scenario: DatabaseScenario, stage: dict, inputs: dict | None = None) -> TranslationJobCreate:
    return TranslationJobCreate.model_validate(
        {
            "novel_id": scenario.novels["novel_1"].novel_id,
            "config": {"batch_size": 100},
            "inputs": inputs or {},
            "stages": [stage],
        }
    )


async def _run_loader(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    request: TranslationJobCreate,
    next_step: str,
    before_load: Callable[[], Awaitable[None]] | None = None,
) -> tuple[list[TranslationRecord], list[UUID], TranslationTask, AsyncMock]:
    job_id = await create_job(db, request)
    rows = (
        await db.execute(
            select(TranslationTask, TranslationStage.action)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    ).all()
    (loader, loader_action), (following, _) = rows
    assert loader_action == "load_inputs"
    assert (loader.status, following.status) == (State.READY, State.WAITING)
    chapter_ids = list(
        await db.scalars(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    )
    store, dispatch = MemoryObjectStore(), AsyncMock()
    monkeypatch.setattr("src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", session_factory)
    monkeypatch.setattr("src.translations.actions.load_inputs.get_async_object_store", lambda: store)
    monkeypatch.setattr(step_task(next_step), "kiq", dispatch)

    if before_load is not None:
        await before_load()
    await run_step(LOAD_INPUTS_LOAD)(loader.task_id)

    await db.refresh(loader)
    await db.refresh(following)
    assert loader.status == State.COMPLETE and loader.output_file_id is not None
    stored = await db.get(StoredFile, loader.output_file_id)
    assert stored is not None
    return list(iter_translation_records([store.objects[stored.object_key]])), chapter_ids, following, dispatch


async def test_loader_captures_every_enabled_stream_and_readies_the_next_stage(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = await _group(async_test_db, sample_scenario)
    inputs = {
        "memories": {
            "type": "memories",
            "memory_group_id": str(group.memory_group_id),
            "exclude_current_chapter": False,
        }
    }
    request = _request(sample_scenario, {"action": "prune_memories", "config": {"model": "qwen-plus"}}, inputs)

    records, chapter_ids, following, dispatch = await _run_loader(
        async_test_db,
        testing_async_session_local,
        monkeypatch,
        request,
        "src.translations.actions.prune_memories.prepare",
    )

    assert {(record.chapter_id, record.stream, record.data_name) for record in records} == {
        (chapter_id, name, name) for chapter_id in chapter_ids for name in ("chapter", "memories")
    }
    assert any(
        isinstance(record, MemoriesRecord)
        and [item.memory_content for item in record.payload] == ["Original candidate"]
        for record in records
    )
    assert following.status == State.READY
    dispatch.assert_called_once_with(str(following.task_id))


async def test_loader_captures_only_chapters_when_no_streams_are_enabled(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(sample_scenario, {"action": "translate", "config": {"model": "qwen-plus"}})

    records, chapter_ids, _, _ = await _run_loader(
        async_test_db, testing_async_session_local, monkeypatch, request, "src.translations.actions.translate.prepare"
    )

    assert all(isinstance(record, ChapterRecord) and record.payload for record in records)
    assert {record.chapter_id for record in records} == set(chapter_ids)


def test_creation_rejects_stages_whose_streams_the_job_does_not_load(sample_scenario: DatabaseScenario) -> None:
    with pytest.raises(ValidationError, match="stage 1 requires memories"):
        _request(sample_scenario, {"action": "prune_memories", "config": {"model": "qwen-plus"}})
    with pytest.raises(ValidationError, match="must be named 'memories'"):
        _request(
            sample_scenario,
            {"action": "translate", "config": {"model": "qwen-plus"}},
            {"side": {"type": "memories", "memory_group_id": "00000000-0000-0000-0000-000000000001"}},
        )


async def test_loader_rejects_a_memory_group_from_another_novel(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The service checks ownership at creation; the loader checks again in case the group moved since.
    group = await _group(async_test_db, sample_scenario)
    inputs = {
        stream: {"type": stream, "memory_group_id": str(group.memory_group_id)}
        for stream in ("memories", "terms", "conventions")
    }
    request = _request(sample_scenario, {"action": "translate", "config": {"model": "qwen-plus"}}, inputs)
    job_id = await create_job(async_test_db, request)
    group.novel_id = sample_scenario.novels["novel_2"].novel_id
    await async_test_db.commit()
    loader = (
        await async_test_db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id, TranslationStage.stage_num == 0)
        )
    ).one()
    store = MemoryObjectStore()
    monkeypatch.setattr(
        "src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", testing_async_session_local
    )
    monkeypatch.setattr("src.translations.actions.load_inputs.get_async_object_store", lambda: store)

    with pytest.raises(ValueError, match="does not belong"):
        await run_step(LOAD_INPUTS_LOAD)(loader.task_id)

    await async_test_db.refresh(loader)
    assert loader.output_file_id is None and loader.failed_at is not None
    assert not store.objects


async def test_loader_snapshots_usable_terms_for_pinned_text_and_global_conventions(
    async_test_db: AsyncSession,
    test_async_engine: AsyncEngine,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = await _group(async_test_db, sample_scenario)
    # Scenario rows belong to the sync session; edit them through the async one.
    source = await async_test_db.get_one(ChapterContent, sample_scenario.contents["chapter_1_v2"].chapter_content_id)
    source.chapter_content_text = "Alpha Approved RejectedTerm RejectedMapping Unmapped"
    chapter_id = source.chapter_id
    other_group = MemoryGroup(novel_id=group.novel_id, memory_group_name="Other", memory_language="en")
    second = Chapter(novel_id=group.novel_id, chapter_num=100, chapter_title="No matches", chapter_is_public=False)
    async_test_db.add_all([other_group, second])
    await async_test_db.flush()
    second_id = second.chapter_id
    async_test_db.add(
        ChapterContent(chapter_id=second_id, chapter_content_version=1, chapter_content_text="No matches")
    )
    for name, term_status, translation_status in [
        ("Alpha", ReviewStatus.PENDING, ReviewStatus.PENDING),
        ("Approved", ReviewStatus.APPROVED, ReviewStatus.APPROVED),
        ("RejectedTerm", ReviewStatus.REJECTED, ReviewStatus.PENDING),
        ("RejectedMapping", ReviewStatus.PENDING, ReviewStatus.REJECTED),
        ("Absent", ReviewStatus.PENDING, ReviewStatus.PENDING),
        ("NewOnly", ReviewStatus.PENDING, ReviewStatus.PENDING),
    ]:
        term = GlossaryTerm(memory_group_id=group.memory_group_id, term=name, review_status=term_status)
        async_test_db.add(term)
        await async_test_db.flush()
        async_test_db.add(
            TermTranslation(
                term_id=term.term_id,
                translation=f"English {name}",
                review_status=translation_status,
                creator_type=Creator.USER,
            )
        )
    async_test_db.add(GlossaryTerm(memory_group_id=group.memory_group_id, term="Unmapped"))
    foreign_term = GlossaryTerm(memory_group_id=other_group.memory_group_id, term="Alpha")
    async_test_db.add(foreign_term)
    await async_test_db.flush()
    async_test_db.add(
        TermTranslation(term_id=foreign_term.term_id, translation="Wrong group", creator_type=Creator.USER)
    )
    for title, category, status, owner in [
        ("Names", ConventionCategory.NAMING, ReviewStatus.PENDING, group),
        ("Voice", ConventionCategory.STYLE, ReviewStatus.APPROVED, group),
        ("Rejected", ConventionCategory.STYLE, ReviewStatus.REJECTED, group),
        ("Foreign", ConventionCategory.NAMING, ReviewStatus.APPROVED, other_group),
    ]:
        async_test_db.add(
            TranslationConvention(
                memory_group_id=owner.memory_group_id,
                category=category,
                title=title,
                rule=f"Rule for {title}",
                rationale=None,
                review_status=status,
                creator_type=Creator.USER,
            )
        )
    await async_test_db.flush()
    inputs = {
        stream: {"type": stream, "memory_group_id": str(group.memory_group_id)} for stream in ("terms", "conventions")
    }
    request = _request(sample_scenario, {"action": "translate", "config": {"model": "qwen-plus"}}, inputs)

    async def edit_after_pinning() -> None:
        async_test_db.add(
            ChapterContent(chapter_id=chapter_id, chapter_content_version=3, chapter_content_text="NewOnly")
        )
        await async_test_db.commit()

    chapter_reads: list[str] = []

    def record_query(conn, cursor, statement, parameters, context, executemany):
        if "chapter_content_text" in statement and "source_chapter_content_id" in statement:
            chapter_reads.append(statement)

    event.listen(test_async_engine.sync_engine, "before_cursor_execute", record_query)
    try:
        records, chapter_ids, following, _ = await _run_loader(
            async_test_db,
            testing_async_session_local,
            monkeypatch,
            request,
            "src.translations.actions.translate.prepare",
            edit_after_pinning,
        )
    finally:
        event.remove(test_async_engine.sync_engine, "before_cursor_execute", record_query)
    assert len(chapter_reads) == 1
    assert {(record.chapter_id, record.stream) for record in records} == {
        (chapter, stream) for chapter in chapter_ids for stream in ("chapter", "terms", "conventions")
    }
    terms = {record.chapter_id: record.payload for record in records if isinstance(record, TermsRecord)}
    assert terms[chapter_id] == {"Alpha": "English Alpha", "Approved": "English Approved"}
    assert terms[second_id] == {}
    conventions = [record for record in records if isinstance(record, ConventionsRecord)]
    assert len(conventions) == len(chapter_ids)
    for record in conventions:
        assert {(item.category, item.title, item.rule, item.rationale) for item in record.payload} == {
            (ConventionCategory.NAMING, "Names", "Rule for Names", None),
            (ConventionCategory.STYLE, "Voice", "Rule for Voice", None),
        }
    assert following.status == State.READY


async def test_loader_emits_empty_records_for_an_independently_enabled_stream(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = await _group(async_test_db, sample_scenario)
    request = _request(
        sample_scenario,
        {"action": "translate", "config": {"model": "qwen-plus"}},
        {"conventions": {"type": "conventions", "memory_group_id": str(group.memory_group_id)}},
    )
    records, chapter_ids, _, _ = await _run_loader(
        async_test_db, testing_async_session_local, monkeypatch, request, "src.translations.actions.translate.prepare"
    )
    assert {(record.chapter_id, record.stream) for record in records} == {
        (chapter, name) for chapter in chapter_ids for name in ("chapter", "conventions")
    }
    assert all(not record.payload for record in records if record.stream == "conventions")
