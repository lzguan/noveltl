import asyncio
from collections.abc import AsyncIterable
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.files.models import StoredFile
from src.translations.actions.execution.async_actions import build_async_registry
from src.translations.clients.batch_jobs import BatchJobId
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationStage, TranslationTask
from src.translations.records import ChapterRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore
from tests.translations.test_pipeline import EchoClient


class FailingClient(EchoClient):
    async def create_batch_job(self, content: AsyncIterable[bytes]) -> BatchJobId:
        raise RuntimeError("provider unavailable")


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryObjectStore:
    store = MemoryObjectStore()
    for module in ("load_inputs", "prune_memories", "translate", "common.staging"):
        monkeypatch.setattr(f"src.translations.actions.{module}.get_async_object_store", lambda: store)
    return store


async def _job(db: AsyncSession, scenario: DatabaseScenario) -> UUID:
    return await create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 1},
                "inputs": {},
                "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}],
            }
        ),
    )


async def _tasks(db: AsyncSession, job_id: UUID, stage_num: int) -> list[TranslationTask]:
    db.expunge_all()
    return list(
        await db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id, TranslationStage.stage_num == stage_num)
        )
    )


async def _run(session_factory: async_sessionmaker[AsyncSession], loader_ids: list[UUID]) -> list[BaseException | None]:
    registry = build_async_registry(session_factory, max_concurrent_steps=2)
    return await asyncio.gather(
        *(registry["load_inputs"].entrypoint(task_id) for task_id in loader_ids), return_exceptions=True
    )


async def test_entrypoint_runs_every_stage_of_each_batch_before_returning(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    sample_scenario: DatabaseScenario,
    store: MemoryObjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = EchoClient()
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", lambda: client)
    # Two jobs give two batches whose chains run concurrently.
    job_ids = [await _job(async_test_db, sample_scenario), await _job(async_test_db, sample_scenario)]
    loaders = [task for job_id in job_ids for task in await _tasks(async_test_db, job_id, 0)]

    results = await _run(testing_async_session_local, [task.task_id for task in loaders])

    assert results == [None] * len(loaders)
    translations = [task for job_id in job_ids for task in await _tasks(async_test_db, job_id, 1)]
    loaded = [task for job_id in job_ids for task in await _tasks(async_test_db, job_id, 0)]
    assert {task.status for task in loaded + translations} == {State.COMPLETE}
    for task in translations:
        assert task.output_file_id is not None
        stored = await async_test_db.get(StoredFile, task.output_file_id)
        assert stored is not None
        records = list(iter_translation_records([store.objects[stored.object_key]]))
        assert [record.payload for record in records if isinstance(record, ChapterRecord)] == ["Translated chapter"]
    assert len(client.batches) == len(loaders)


async def test_step_failure_is_recorded_and_raised_from_entrypoint(
    async_test_db: AsyncSession,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    sample_scenario: DatabaseScenario,
    store: MemoryObjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", FailingClient)
    job_id = await _job(async_test_db, sample_scenario)
    loaders = await _tasks(async_test_db, job_id, 0)

    results = await _run(testing_async_session_local, [task.task_id for task in loaders])

    assert all(isinstance(result, RuntimeError) and str(result) == "provider unavailable" for result in results)
    assert {task.status for task in await _tasks(async_test_db, job_id, 0)} == {State.COMPLETE}
    for task in await _tasks(async_test_db, job_id, 1):
        assert task.status == State.SUBMITTING and task.failed_at is not None
