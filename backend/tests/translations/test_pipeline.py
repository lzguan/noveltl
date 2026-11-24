import json
from collections.abc import AsyncIterable, AsyncIterator
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, MemoryType
from src.novels.models import ChapterContent
from src.translations.celery_app import app
from src.translations.clients.batch_jobs import BatchJobComplete, BatchJobId, BatchJobPoll, BatchOutputId
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.task_names import (
    LOAD_INPUTS_LOAD,
    PRUNE_MEMORIES_FINALIZE,
    PRUNE_MEMORIES_POLL,
    PRUNE_MEMORIES_PREPARE,
    PRUNE_MEMORIES_SUBMIT,
    TRANSLATE_FINALIZE,
    TRANSLATE_POLL,
    TRANSLATE_PREPARE,
    TRANSLATE_SUBMIT,
)
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.steps import celery_step
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore

CANDIDATES = ("First candidate", "Second candidate")


class EchoClient:
    def __init__(self) -> None:
        self.batches: list[list[dict]] = []

    async def create_batch_job(self, content: AsyncIterable[bytes]) -> BatchJobId:
        self.batches.append([json.loads(line) for line in b"".join([chunk async for chunk in content]).splitlines()])
        return BatchJobId(str(len(self.batches) - 1))

    async def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        return BatchJobComplete(BatchOutputId(job_id))

    async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
        for request in self.batches[int(output_id)]:
            system = request["body"]["messages"][0]["content"]
            text = "[0]" if system.startswith("Select the context memories") else "Translated chapter"
            body = {
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]
            }
            yield (
                json.dumps({"custom_id": request["custom_id"], "response": {"status_code": 200, "body": body}}).encode()
                + b"\n"
            )


@pytest.fixture
def pipeline(
    test_db: Session, testing_async_session_local: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> tuple[MemoryObjectStore, EchoClient]:
    store, client = MemoryObjectStore(), EchoClient()
    monkeypatch.setattr("src.translations.actions.celery_actions.CelerySessionLocal", testing_async_session_local)
    for module in ("load_inputs", "prune_memories", "translate"):
        monkeypatch.setattr(f"src.translations.actions.{module}.get_async_object_store", lambda: store)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    for name, task in app.tasks.items():
        if name.startswith("src.translations.actions."):
            monkeypatch.setattr(task, "apply_async", Mock())
    return store, client


async def _tasks(
    db: AsyncSession, scenario: DatabaseScenario, stages: list[dict], inputs: dict
) -> list[TranslationTask]:
    job_id = await create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 100},
                "inputs": inputs,
                "stages": stages,
            }
        ),
    )
    assert await db.scalar(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    return list(
        await db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    )


async def _output(db: AsyncSession, store: MemoryObjectStore, task: TranslationTask) -> list[TranslationRecord]:
    await db.refresh(task)
    assert task.status == State.COMPLETE and task.output_file_id is not None
    stored = await db.get(StoredFile, task.output_file_id)
    assert stored is not None
    return list(iter_translation_records([store.objects[stored.object_key]]))


async def test_job_loads_prunes_and_translates_with_each_stage_carrying_the_full_state(
    async_test_db: AsyncSession, sample_scenario: DatabaseScenario, pipeline: tuple[MemoryObjectStore, EchoClient]
) -> None:
    store, client = pipeline
    novel = sample_scenario.novels["novel_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Pipeline", memory_language=novel.language_code)
    async_test_db.add(group)
    await async_test_db.flush()
    for content in CANDIDATES:
        async_test_db.add(
            Memory(
                memory_group_id=group.memory_group_id,
                memory_observed_in=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
                memory_type=MemoryType.FACT,
                memory_content=content,
                memory_start_num=0,
                creator_type=Creator.USER,
                plugin_name="continuity",
            )
        )
    await async_test_db.flush()
    # Scenario rows belong to the sync session; edit them through the async one.
    source = await async_test_db.get_one(ChapterContent, sample_scenario.contents["chapter_1_v2"].chapter_content_id)
    source.chapter_content_text = "白玫 arrives."
    term = GlossaryTerm(memory_group_id=group.memory_group_id, term="白玫")
    async_test_db.add(term)
    await async_test_db.flush()
    async_test_db.add(TermTranslation(term_id=term.term_id, translation="White Rose", creator_type=Creator.USER))
    async_test_db.add(
        TranslationConvention(
            memory_group_id=group.memory_group_id,
            category=ConventionCategory.STYLE,
            title="Narrator",
            rule="Keep the narration restrained.",
            rationale=None,
            creator_type=Creator.USER,
        )
    )
    inputs = {
        "memories": {
            "type": "memories",
            "memory_group_id": str(group.memory_group_id),
            "exclude_current_chapter": False,
        },
        "terms": {"type": "terms", "memory_group_id": str(group.memory_group_id)},
        "conventions": {"type": "conventions", "memory_group_id": str(group.memory_group_id)},
    }
    stages = [
        {"action": "prune_memories", "config": {"model": "qwen-plus"}},
        {"action": "translate", "config": {"model": "qwen-plus"}},
        {"action": "translate", "config": {"model": "qwen-plus"}},
    ]
    loader, pruning, translation, revision = await _tasks(async_test_db, sample_scenario, stages, inputs)

    await celery_step(LOAD_INPUTS_LOAD)(loader.task_id)
    for step in (PRUNE_MEMORIES_PREPARE, PRUNE_MEMORIES_SUBMIT, PRUNE_MEMORIES_POLL, PRUNE_MEMORIES_FINALIZE):
        await celery_step(step)(pruning.task_id)
    for step in (TRANSLATE_PREPARE, TRANSLATE_SUBMIT, TRANSLATE_POLL, TRANSLATE_FINALIZE):
        await celery_step(step)(translation.task_id)
    for step in (TRANSLATE_PREPARE, TRANSLATE_SUBMIT, TRANSLATE_POLL, TRANSLATE_FINALIZE):
        await celery_step(step)(revision.task_id)

    loaded = await _output(async_test_db, store, loader)
    pruned = await _output(async_test_db, store, pruning)
    translated = await _output(async_test_db, store, translation)
    revised = await _output(async_test_db, store, revision)
    chapter_ids = {record.chapter_id for record in loaded}
    expected_keys = {
        (chapter_id, stream) for chapter_id in chapter_ids for stream in ("chapter", "memories", "terms", "conventions")
    }
    # Every stage's file is the full state: its own outputs plus everything it left alone.
    for output in (loaded, pruned, translated, revised):
        assert {(record.chapter_id, record.stream) for record in output} == expected_keys
        assert [record for record in output if record.stream in ("terms", "conventions")] == [
            record for record in loaded if record.stream in ("terms", "conventions")
        ]

    def chapters(records: list[TranslationRecord]) -> dict:
        return {record.chapter_id: record.payload for record in records if isinstance(record, ChapterRecord)}

    def memories(records: list[TranslationRecord]) -> dict:
        return {record.chapter_id: record.payload for record in records if isinstance(record, MemoriesRecord)}

    source_text, kept = chapters(loaded), memories(pruned)
    assert chapters(pruned) == source_text
    assert all(len(payload) <= 1 for payload in kept.values()) and any(kept.values())
    assert set(chapters(translated).values()) == {"Translated chapter"}
    assert memories(translated) == kept

    prompts = [request["body"]["messages"][1]["content"] for request in client.batches[1]]
    assert len(prompts) == len(chapter_ids)
    for prompt in prompts:
        # Pruning kept one of the two candidates, and translation saw only that one.
        assert prompt.startswith("Context memories:") and sum(name in prompt for name in CANDIDATES) <= 1
        assert any(text in prompt for text in source_text.values())
    assert any(name in prompt for prompt in prompts for name in CANDIDATES)
    for batch in client.batches[1:]:
        for request in batch:
            prompt = request["body"]["messages"][1]["content"]
            assert "Canonical term translations:" in prompt and "Translation conventions:" in prompt
            assert "Keep the narration restrained." in prompt
        assert any("White Rose" in request["body"]["messages"][1]["content"] for request in batch)
    assert all(
        request["body"]["messages"][1]["content"].endswith("Translated chapter") for request in client.batches[2]
    )


async def test_translation_without_a_memories_stream_sends_only_the_chapter(
    async_test_db: AsyncSession, sample_scenario: DatabaseScenario, pipeline: tuple[MemoryObjectStore, EchoClient]
) -> None:
    store, client = pipeline
    loader, translation = await _tasks(
        async_test_db, sample_scenario, [{"action": "translate", "config": {"model": "qwen-plus"}}], {}
    )

    await celery_step(LOAD_INPUTS_LOAD)(loader.task_id)
    for step in (TRANSLATE_PREPARE, TRANSLATE_SUBMIT, TRANSLATE_POLL, TRANSLATE_FINALIZE):
        await celery_step(step)(translation.task_id)

    source = {record.chapter_id: record.payload for record in await _output(async_test_db, store, loader)}
    assert {request["body"]["messages"][1]["content"] for request in client.batches[0]} == set(source.values())
    assert all("context memories" not in request["body"]["messages"][0]["content"] for request in client.batches[0])
    assert {record.chapter_id for record in await _output(async_test_db, store, translation)} == set(source)
