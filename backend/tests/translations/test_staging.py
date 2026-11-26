import importlib.util
import json
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.schema import CreateSchema

from src.files.access import insert_file, upload_file
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.files import store_lines
from src.translations.actions.common.staging import stage_chapter_outputs
from src.translations.clients.batch_jobs import BatchOutputId
from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.jsonl import encode_translation_record
from src.translations.models import (
    TranslationChapterOutput,
    TranslationJobChapter,
    TranslationStage,
    TranslationTask,
)
from src.translations.records import ChapterRecord
from src.translations.schemas import TranslationJobCreate
from src.translations.task_names import TRANSLATE_FINALIZE
from src.translations.tasks.claims import TranslationClaimLostError
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.steps import run_step, step_task
from test_support.test_data.scenarios import DatabaseScenario
from tests.files.test_access import MemoryObjectStore
from tests.translations.test_translate import FakeBatchClient

finalize = run_step(TRANSLATE_FINALIZE)


async def _seed_translate_job(
    db: AsyncSession,
    scenario: DatabaseScenario,
    store: MemoryObjectStore,
    *,
    stage_count: int = 1,
) -> tuple[UUID, list[TranslationTask], list[UUID]]:
    stages = [{"action": "translate", "config": {"model": "qwen-plus"}} for _ in range(stage_count)]
    job_id = await create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 10},
                "stages": stages,
            }
        ),
    )
    tasks = list(
        await db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    )
    loader, *translate_tasks = tasks
    chapter_ids = sorted(
        await db.scalars(select(TranslationJobChapter.chapter_id).where(TranslationJobChapter.job_id == job_id))
    )
    uploaded = await upload_file(
        store,
        BytesIO(
            b"".join(
                encode_translation_record(ChapterRecord(chapter_id=chapter_id, stream="chapter", payload="Source"))
                for chapter_id in chapter_ids
            )
        ),
        storage_name="test",
        bucket="test",
        namespace="translations",
        content_type="application/jsonl",
    )
    loaded_file_id = await insert_file(db, uploaded)
    loader.status, loader.output_file_id = State.COMPLETE, loaded_file_id
    translate_tasks[0].status = State.PROCESSED
    translate_tasks[0].provider_output_id = "provider-output"
    await db.commit()
    return job_id, translate_tasks, chapter_ids


def _output_client(chapter_ids: list[UUID], translated_text: str) -> type[FakeBatchClient]:
    payload = b"".join(
        json.dumps(
            {
                "custom_id": json.dumps({"chapter_id": str(chapter_id), "stream": "chapter"}),
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": f"{translated_text} {i}"},
                                "finish_reason": "stop",
                            }
                        ]
                    },
                },
            }
        ).encode()
        + b"\n"
        for i, chapter_id in enumerate(chapter_ids)
    )

    class OutputClient(FakeBatchClient):
        async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
            yield payload

    return OutputClient


async def test_stage_chapter_outputs_stages_final_stage_and_upserts_on_retry(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryObjectStore()
    monkeypatch.setattr(
        "src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", testing_async_session_local
    )
    monkeypatch.setattr("src.translations.actions.translate.get_async_object_store", lambda: store)
    monkeypatch.setattr("src.translations.actions.common.staging.get_async_object_store", lambda: store)

    job_id, (task,), chapter_ids = await _seed_translate_job(async_test_db, sample_scenario, store, stage_count=1)
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", _output_client(chapter_ids, "First draft"))

    await finalize(task.task_id)

    async_test_db.expunge_all()
    rows = list(
        await async_test_db.scalars(
            select(TranslationChapterOutput)
            .where(TranslationChapterOutput.job_id == job_id)
            .order_by(TranslationChapterOutput.chapter_id)
        )
    )
    assert [(row.chapter_id, row.stage_id, row.translated_text) for row in rows] == [
        (chapter_id, task.stage_id, f"First draft {i}") for i, chapter_id in enumerate(chapter_ids)
    ]

    # Re-running finalization (retry) must overwrite staged outputs in place.
    refreshed = await async_test_db.get(TranslationTask, task.task_id)
    assert refreshed is not None
    refreshed.status = State.PROCESSED
    await async_test_db.commit()

    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", _output_client(chapter_ids, "Revised draft"))
    await finalize(task.task_id)

    async_test_db.expunge_all()
    updated_rows = list(
        await async_test_db.scalars(
            select(TranslationChapterOutput)
            .where(TranslationChapterOutput.job_id == job_id)
            .order_by(TranslationChapterOutput.chapter_id)
        )
    )
    assert [(row.chapter_id, row.stage_id, row.translated_text) for row in updated_rows] == [
        (chapter_id, task.stage_id, f"Revised draft {i}") for i, chapter_id in enumerate(chapter_ids)
    ]
    assert [row.created_at for row in updated_rows] == [row.created_at for row in rows]
    assert all(updated.updated_at >= original.updated_at for updated, original in zip(updated_rows, rows, strict=True))


async def test_stage_chapter_outputs_rolls_back_task_and_outputs_when_claim_is_lost(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryObjectStore()
    monkeypatch.setattr(
        "src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", testing_async_session_local
    )
    monkeypatch.setattr("src.translations.actions.translate.get_async_object_store", lambda: store)
    monkeypatch.setattr("src.translations.actions.common.staging.get_async_object_store", lambda: store)

    job_id, (task,), chapter_ids = await _seed_translate_job(async_test_db, sample_scenario, store, stage_count=1)
    base_client = _output_client(chapter_ids, "Stale worker")

    class StealingClient(base_client):
        async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
            async with testing_async_session_local.begin() as other_session:
                stolen = await other_session.get(TranslationTask, task.task_id)
                assert stolen is not None
                stolen.claim_token = uuid4()
            async for chunk in super().fetch_batch_output(output_id):
                yield chunk

    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", StealingClient)

    with pytest.raises(TranslationClaimLostError):
        await finalize(task.task_id)

    async_test_db.expunge_all()
    refreshed = await async_test_db.get(TranslationTask, task.task_id)
    assert refreshed is not None
    assert refreshed.output_file_id is None
    assert refreshed.status == State.FINALIZING
    staged_count = await async_test_db.scalar(
        select(func.count()).select_from(TranslationChapterOutput).where(TranslationChapterOutput.job_id == job_id)
    )
    assert staged_count == 0


async def test_stage_chapter_outputs_keeps_separate_rows_per_stage(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryObjectStore()
    monkeypatch.setattr(
        "src.translations.actions.execution.taskiq_actions.TaskiqSessionLocal", testing_async_session_local
    )
    monkeypatch.setattr("src.translations.actions.translate.get_async_object_store", lambda: store)
    monkeypatch.setattr("src.translations.actions.common.staging.get_async_object_store", lambda: store)
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", AsyncMock())

    job_id, (first_task, second_task), chapter_ids = await _seed_translate_job(
        async_test_db, sample_scenario, store, stage_count=2
    )
    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", _output_client(chapter_ids, "Stage 1"))

    await finalize(first_task.task_id)

    refreshed_second = await async_test_db.get(TranslationTask, second_task.task_id)
    assert refreshed_second is not None
    refreshed_second.status = State.PROCESSED
    refreshed_second.provider_output_id = "provider-output-stage-2"
    await async_test_db.commit()

    monkeypatch.setitem(BATCH_CLIENT_FACTORIES, "qwen-plus", _output_client(chapter_ids, "Stage 2"))
    await finalize(second_task.task_id)

    async_test_db.expunge_all()
    stage1_rows = list(
        await async_test_db.scalars(
            select(TranslationChapterOutput)
            .where(
                TranslationChapterOutput.job_id == job_id,
                TranslationChapterOutput.stage_id == first_task.stage_id,
            )
            .order_by(TranslationChapterOutput.chapter_id)
        )
    )
    stage2_rows = list(
        await async_test_db.scalars(
            select(TranslationChapterOutput)
            .where(
                TranslationChapterOutput.job_id == job_id,
                TranslationChapterOutput.stage_id == second_task.stage_id,
            )
            .order_by(TranslationChapterOutput.chapter_id)
        )
    )
    assert [(row.chapter_id, row.translated_text) for row in stage1_rows] == [
        (chapter_id, f"Stage 1 {i}") for i, chapter_id in enumerate(chapter_ids)
    ]
    assert [(row.chapter_id, row.translated_text) for row in stage2_rows] == [
        (chapter_id, f"Stage 2 {i}") for i, chapter_id in enumerate(chapter_ids)
    ]


async def test_stage_chapter_outputs_releases_db_transaction_during_storage_fetch(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_in_txn: list[bool] = []

    class ObservingStore(MemoryObjectStore):
        async def fetch(self, key: str, *, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
            observed_in_txn.append(async_test_db.in_transaction())
            async for chunk in super().fetch(key, chunk_size=chunk_size):
                yield chunk

    store = ObservingStore()
    monkeypatch.setattr("src.translations.actions.common.staging.get_async_object_store", lambda: store)
    job_id, (task,), chapter_ids = await _seed_translate_job(async_test_db, sample_scenario, store, stage_count=1)
    async_test_db.expunge(task)
    context = ActionTaskContext(db=async_test_db, task=task)

    @stage_chapter_outputs
    async def produce(ctx: ActionTaskContext) -> None:
        async def lines() -> AsyncIterator[bytes]:
            for chapter_id in chapter_ids:
                yield encode_translation_record(ChapterRecord(chapter_id=chapter_id, stream="chapter", payload="Clean"))

        ctx.task.output_file_id = await store_lines(ctx, store, lines())

    await produce(context)

    assert observed_in_txn == [False]
    assert async_test_db.in_transaction()
    staged_count = await async_test_db.scalar(
        select(func.count()).select_from(TranslationChapterOutput).where(TranslationChapterOutput.job_id == job_id)
    )
    assert staged_count == len(chapter_ids)
    await async_test_db.rollback()


def test_staging_migration_backfills_chapter_num_and_round_trips(test_engine: Engine) -> None:
    path = Path(__file__).parents[2] / "alembic/versions/e3f8b1c4a7d2_add_translation_staging_and_accepts.py"
    spec = importlib.util.spec_from_file_location("staging_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    novel_id, chapter_id, content_id, job_id, stage_id, batch_id = (uuid4() for _ in range(6))
    conn = test_engine.connect()
    transaction = conn.begin()
    try:
        schema = "staging_migration_" + uuid4().hex
        conn.execute(CreateSchema(schema))
        conn.execute(select(func.set_config("search_path", schema, True)))
        conn.execute(text("CREATE TABLE novels (novel_id uuid PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE chapters (chapter_id uuid PRIMARY KEY, chapter_num integer NOT NULL)"))
        conn.execute(text("CREATE TABLE chapter_contents (chapter_content_id uuid PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE translation_jobs (job_id uuid PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE translation_stages (stage_id uuid PRIMARY KEY, job_id uuid NOT NULL)"))
        conn.execute(text("CREATE TABLE translation_batches (batch_id uuid PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE translation_job_chapters ("
                "job_id uuid NOT NULL, chapter_id uuid NOT NULL, "
                "source_chapter_content_id uuid NOT NULL, batch_id uuid NOT NULL, "
                "PRIMARY KEY (job_id, chapter_id))"
            )
        )
        conn.execute(text("INSERT INTO novels VALUES (:id)"), {"id": novel_id})
        conn.execute(text("INSERT INTO chapters VALUES (:id, 7)"), {"id": chapter_id})
        conn.execute(text("INSERT INTO chapter_contents VALUES (:id)"), {"id": content_id})
        conn.execute(text("INSERT INTO translation_jobs VALUES (:id)"), {"id": job_id})
        conn.execute(text("INSERT INTO translation_stages VALUES (:id, :job)"), {"id": stage_id, "job": job_id})
        conn.execute(text("INSERT INTO translation_batches VALUES (:id)"), {"id": batch_id})
        conn.execute(
            text("INSERT INTO translation_job_chapters VALUES (:job, :chapter, :content, :batch)"),
            {"job": job_id, "chapter": chapter_id, "content": content_id, "batch": batch_id},
        )

        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert conn.scalar(text("SELECT chapter_num FROM translation_job_chapters")) == 7
            tables = set(
                conn.scalars(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
                )
            )
            assert {"translation_chapter_outputs", "translation_chapter_accepts"} <= tables

            migration.downgrade()
            cols = set(
                conn.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = 'translation_job_chapters'"
                    )
                )
            )
            assert "chapter_num" not in cols
            tables_after = set(
                conn.scalars(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
                )
            )
            assert "translation_chapter_outputs" not in tables_after
            assert "translation_chapter_accepts" not in tables_after
    finally:
        transaction.rollback()
        conn.close()
