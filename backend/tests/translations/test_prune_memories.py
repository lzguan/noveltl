import json
from collections.abc import AsyncIterable, AsyncIterator
from io import BytesIO
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.files.access import create_file
from src.files.models import StoredFile
from src.memory.models import Memory, MemoryGroup
from src.memory.schemas import Memory as MemorySchema
from src.memory.types import Creator, MemoryType
from src.translations.celery_app import app
from src.translations.clients.batch_jobs import BatchJobComplete, BatchJobId, BatchJobPoll, BatchOutputId
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.models import TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.task_names import (
    PRUNE_MEMORIES_FINALIZE,
    PRUNE_MEMORIES_POLL,
    PRUNE_MEMORIES_PREPARE,
    PRUNE_MEMORIES_SUBMIT,
)
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.steps import celery_step
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore

# The registered Celery tasks: claim, run the step, then dispatch the next one.
prepare, submit, poll, finalize = (
    celery_step(name)
    for name in (PRUNE_MEMORIES_PREPARE, PRUNE_MEMORIES_SUBMIT, PRUNE_MEMORIES_POLL, PRUNE_MEMORIES_FINALIZE)
)


class PruningClient:
    def __init__(self, response: str) -> None:
        self.requests: list[dict] = []
        self.response = response

    async def create_batch_job(self, content: AsyncIterable[bytes]) -> BatchJobId:
        self.requests = [json.loads(line) for line in b"".join([chunk async for chunk in content]).splitlines()]
        return BatchJobId("pruning-job")

    async def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        assert job_id == "pruning-job"
        return BatchJobComplete(BatchOutputId("pruning-output"))

    async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
        assert output_id == "pruning-output"
        output = b"".join(
            json.dumps(
                {
                    "custom_id": request["custom_id"],
                    "response": {
                        "status_code": 200,
                        "body": {
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {"role": "assistant", "content": self.response},
                                    "finish_reason": "stop",
                                }
                            ]
                        },
                    },
                }
            ).encode()
            + b"\n"
            for request in reversed(self.requests)
        )
        for offset in range(0, len(output), 7):
            yield output[offset : offset + 7]


def _by_key(records: list[TranslationRecord]) -> list[TranslationRecord]:
    return sorted(records, key=lambda record: (record.stream, record.chapter_id))


@pytest.mark.parametrize("response", ["[0]", "[]", "[99]", "[true]", "prepare_upload"])
async def test_pruning_resolves_loaded_candidates_and_advances_only_valid_output(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    response: str,
) -> None:
    # The model's indices must resolve against the candidates the previous stage
    # wrote, even after DB memory content changes. DB transactions are real; the
    # unavailable provider, S3, and queue dispatch are external test seams.
    novel = sample_scenario.novels["novel_1"]
    group = MemoryGroup(novel_id=novel.novel_id, memory_group_name="Pruning", memory_language=novel.language_code)
    async_test_db.add(group)
    await async_test_db.flush()
    memory = Memory(
        memory_group_id=group.memory_group_id,
        memory_observed_in=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
        memory_type=MemoryType.FACT,
        memory_content="Original candidate",
        memory_start_num=0,
        creator_type=Creator.USER,
        plugin_name="continuity",
    )
    async_test_db.add(memory)
    await async_test_db.flush()
    candidate = MemorySchema.model_validate(memory)
    job_id = await create_job(
        async_test_db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": novel.novel_id,
                "config": {"batch_size": 10},
                "inputs": {"memories": {"type": "memories", "memory_group_id": str(group.memory_group_id)}},
                "stages": [
                    {"action": "prune_memories", "config": {"model": "qwen-plus"}},
                    {"action": "translate", "config": {"model": "qwen-plus"}},
                ],
            }
        ),
    )
    loader, task, following = (
        await async_test_db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    ).all()
    task_id, following_id = task.task_id, following.task_id
    chapter_ids = list(
        await async_test_db.scalars(
            select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id)
        )
    )
    chapters: list[TranslationRecord] = [
        ChapterRecord(chapter_id=chapter_id, stream="chapter", payload="Loaded chapter") for chapter_id in chapter_ids
    ]
    candidates: list[TranslationRecord] = [
        MemoriesRecord(chapter_id=chapter_id, stream="memories", payload=[candidate]) for chapter_id in chapter_ids
    ]
    store = MemoryObjectStore()
    loaded = await create_file(
        async_test_db,
        store,
        BytesIO(b"".join(encode_translation_record(record) for record in chapters + candidates)),
        storage_name="test",
        bucket="test",
        namespace="translations",
        content_type="application/jsonl",
    )
    await async_test_db.flush()
    loader.status, loader.output_file_id = State.COMPLETE, loaded.file_id
    task.status = State.READY
    await async_test_db.commit()
    monkeypatch.setattr("src.translations.actions.celery_actions.CelerySessionLocal", testing_async_session_local)
    monkeypatch.setattr("src.translations.actions.prune_memories.get_async_object_store", lambda: store)
    client = PruningClient(response)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    for name in ("submit", "poll", "finalize"):
        monkeypatch.setattr(app.tasks[f"src.translations.actions.prune_memories.{name}"], "apply_async", Mock())

    def check_dispatch(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            completed = db.get(TranslationTask, task_id)
            next_task = db.get(TranslationTask, following_id)
            assert completed is not None and completed.status == State.COMPLETE and completed.output_file_id is not None
            assert next_task is not None and next_task.status == State.READY

    dispatch = Mock(side_effect=check_dispatch)
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", dispatch)
    if response == "prepare_upload":
        store.upload_error = ConnectionError("upload interrupted")
        with pytest.raises(ConnectionError, match="upload interrupted"):
            await prepare(task_id)
        await async_test_db.refresh(task)
        assert task.request_file_id is None
        assert task.failed_at is not None and task.status == State.PREPARING
        # Only the loader's file exists.
        assert await async_test_db.scalar(select(func.count()).select_from(StoredFile)) == 1
        dispatch.assert_not_called()
        return
    await prepare(task_id)
    await async_test_db.refresh(task)
    assert task.status == State.PREPARED and task.request_file_id is not None
    memory.memory_content = "Changed after loading"
    await async_test_db.commit()
    await submit(task_id)
    assert len(client.requests) == len(chapter_ids)
    for request in client.requests:
        assert json.loads(request["custom_id"])["stream"] == "memories"
        prompt = request["body"]["messages"][1]["content"]
        assert "Original candidate" in prompt and str(memory.memory_id) not in prompt
        assert "Loaded chapter" in prompt
    await poll(task_id)
    count_before = await async_test_db.scalar(select(func.count()).select_from(StoredFile))
    if response in ("[99]", "[true]"):
        with pytest.raises(ValueError):
            await finalize(task_id)
        await async_test_db.refresh(task)
        await async_test_db.refresh(following)
        assert task.failed_at is not None and task.status == State.FINALIZING
        assert task.output_file_id is None and following.status == State.WAITING
        assert await async_test_db.scalar(select(func.count()).select_from(StoredFile)) == count_before
        dispatch.assert_not_called()
        return
    await finalize(task_id)
    await async_test_db.refresh(task)
    assert task.status == State.COMPLETE and task.output_file_id is not None
    output = await async_test_db.get(StoredFile, task.output_file_id)
    assert output is not None
    # The output is the full state: chapters copied forward, memories cut to the selection.
    selected: list[TranslationRecord] = (
        candidates
        if response == "[0]"
        else [MemoriesRecord(chapter_id=chapter_id, stream="memories", payload=[]) for chapter_id in chapter_ids]
    )
    records = list(iter_translation_records([store.objects[output.object_key]]))
    assert _by_key(records) == _by_key(chapters + selected)
    dispatch.assert_called_once_with((following_id,))
