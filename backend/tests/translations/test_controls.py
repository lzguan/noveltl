import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.auth.utils import create_access_token
from src.translations.actions import translate
from src.translations.actions.registry import resume_step
from src.translations.actions.taskiq_actions import TaskiqActionCallbacks
from src.translations.models import TranslationBatch, TranslationStage, TranslationTask
from src.translations.schemas import TranslationJobCreate
from src.translations.service import Control, control_translation_job
from src.translations.tasks.claims import TranslationClaimLostError, finish_claim
from src.translations.tasks.jobs import create_job
from src.translations.types import TranslationTaskStatus as State
from test_support.steps import step_task
from test_support.test_data.scenarios import DatabaseScenario


async def make_job(
    db: AsyncSession, scenario: DatabaseScenario, *, loaded: bool = True
) -> tuple[UUID, list[TranslationTask]]:
    job_id = await create_job(
        db,
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 10},
                "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}] * 2,
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
    if loaded:
        # Most tests exercise controls on the user's stages, so the loader has already finished.
        loader, *tasks = tasks
        loader.status, tasks[0].status = State.COMPLETE, State.READY
        await db.commit()
    return job_id, tasks


@pytest.mark.parametrize(
    "state,expected",
    [
        (State.READY, State.READY),
        (State.PREPARING, State.READY),
        (State.PREPARED, State.PREPARED),
        (State.SUBMITTING, State.PREPARED),
        (State.PROCESSING, State.PROCESSING),
        (State.PROCESSED, State.PROCESSED),
        (State.FINALIZING, State.PROCESSED),
    ],
)
def test_registered_steps_resolve_recovery_boundaries(state: State, expected: State) -> None:
    for action in ("translate", "prune_memories"):
        step = resume_step(action, state)
        assert step is not None and step.expect == expected
    loader = resume_step("load_inputs", State.FINALIZING)
    assert loader is not None and loader.expect == State.READY
    assert resume_step("translate", State.COMPLETE) is None


async def test_cancel_fences_worker_and_retry_preserves_provider_output(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, following) = await make_job(async_test_db, sample_scenario)
    user = sample_scenario.users["admin"]
    token = uuid4()
    current.status, current.provider_batch_id, current.provider_output_id = State.FINALIZING, "provider", "output"
    current.claim_token = token
    current.claim_expires_at = await async_test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=5)
    await async_test_db.commit()
    # The operator can cancel a live worker. Its token must no longer commit.
    cancelled = await control_translation_job(async_test_db, user, job_id, "cancel", batch_id=current.batch_id)
    assert cancelled.affected_batch_ids == [current.batch_id]
    await async_test_db.refresh(current)
    await async_test_db.refresh(following)
    assert current.claim_token is None and current.status == State.FINALIZING and current.failed_at is not None
    assert following.failed_at is not None and following.status == State.WAITING
    async with testing_async_session_local.begin() as db:
        with pytest.raises(TranslationClaimLostError):
            await finish_claim(db, current.task_id, token, during=State.FINALIZING, finish=State.COMPLETE)
    assert not (await control_translation_job(async_test_db, user, job_id, "resume")).affected_batch_ids

    # A blocking read is fine here: the test owns the loop while the kick is observed.
    def observe(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            task = db.get(TranslationTask, current.task_id)
            next_task = db.get(TranslationTask, following.task_id)
            assert task is not None and task.status == State.PROCESSED and task.failed_at is None
            assert task.provider_output_id == "output"
            assert next_task is not None and next_task.failed_at is None and next_task.status == State.WAITING

    queued = AsyncMock(side_effect=observe)
    monkeypatch.setattr(step_task("src.translations.actions.translate.finalize"), "kiq", queued)
    retried = await control_translation_job(async_test_db, user, job_id, "retry", batch_id=current.batch_id)
    assert retried.dispatched_task_ids == [current.task_id]
    queued.assert_called_once_with(str(current.task_id))


async def test_resume_skips_live_claim_then_resumes_expired_poll_and_reports_broker_failure(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, _) = await make_job(async_test_db, sample_scenario)
    current.status, current.provider_batch_id = State.PROCESSING, "provider"
    current.claim_token = uuid4()
    current.claim_expires_at = await async_test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=5)
    await async_test_db.commit()
    queued = AsyncMock(side_effect=ConnectionError("broker unavailable"))
    monkeypatch.setattr(step_task("src.translations.actions.translate.poll"), "kiq", queued)
    user = sample_scenario.users["admin"]
    for operation in ("resume", "retry"):
        assert not (await control_translation_job(async_test_db, user, job_id, operation)).affected_batch_ids
    queued.assert_not_called()
    current.claim_expires_at = await async_test_db.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)
    await async_test_db.commit()
    result = await control_translation_job(async_test_db, user, job_id, "resume")
    assert result.dispatch_failed_task_ids == [current.task_id] and not result.dispatched_task_ids
    await async_test_db.refresh(current)
    assert current.claim_token is None and current.failed_at is None and current.status == State.PROCESSING
    queued.side_effect = None
    assert (await control_translation_job(async_test_db, user, job_id, "resume")).dispatched_task_ids == [
        current.task_id
    ]


async def test_cancel_fences_inflight_exitpoint(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, following) = await make_job(async_test_db, sample_scenario)
    current.status = State.COMPLETE
    await async_test_db.commit()
    current_id = current.task_id
    monkeypatch.setattr("src.translations.actions.taskiq_actions.TaskiqSessionLocal", testing_async_session_local)
    queued = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", queued)
    # Hold the next task's row lock so the exitpoint blocks inside its READY update.
    await async_test_db.execute(
        update(TranslationTask).where(TranslationTask.task_id == following.task_id).values(error="pending cancel")
    )
    entered = Event()
    engine = testing_async_session_local.kw["bind"].sync_engine

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE translation_tasks") and parameters.get("status") == State.READY:
            entered.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        callbacks = translate.callbacks
        assert isinstance(callbacks, TaskiqActionCallbacks)
        worker = asyncio.create_task(callbacks.exitpoint(current_id))
        try:
            async with asyncio.timeout(5):
                while not entered.is_set():
                    await asyncio.sleep(0.01)
            await control_translation_job(async_test_db, sample_scenario.users["admin"], job_id, "cancel")
        finally:
            await async_test_db.rollback()  # Release the lock even if the test fails.
        await asyncio.wait_for(worker, 5)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    await async_test_db.refresh(following)
    assert following.status == State.WAITING and following.failed_at is not None
    queued.assert_not_called()


async def test_controls_isolate_batches_and_resume_later_stage(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (first, second) = await make_job(async_test_db, sample_scenario)
    other_batch = TranslationBatch(job_id=job_id, batch_num=1)
    async_test_db.add(other_batch)
    await async_test_db.flush()
    completed = TranslationTask(batch_id=other_batch.batch_id, stage_id=first.stage_id, status=State.COMPLETE)
    waiting = TranslationTask(batch_id=other_batch.batch_id, stage_id=second.stage_id, status=State.WAITING)
    async_test_db.add_all([completed, waiting])
    await async_test_db.commit()
    queued = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", queued)
    user = sample_scenario.users["admin"]
    await control_translation_job(async_test_db, user, job_id, "cancel", batch_id=first.batch_id)
    resumed = await control_translation_job(async_test_db, user, job_id, "resume")
    assert resumed.dispatched_task_ids == [waiting.task_id]
    await async_test_db.refresh(waiting)
    assert waiting.status == State.READY and waiting.failed_at is None
    await async_test_db.refresh(first)
    assert first.failed_at is not None
    waiting.status = State.COMPLETE
    await async_test_db.commit()
    retried = await control_translation_job(async_test_db, user, job_id, "retry")
    assert retried.dispatched_task_ids == [first.task_id]
    assert retried.affected_batch_ids == [first.batch_id]


async def test_retry_preparation_discards_stale_provider_ids(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (task, _) = await make_job(async_test_db, sample_scenario)
    task.status = State.PREPARING
    task.failed_at = await async_test_db.scalar(select(func.clock_timestamp()))
    task.provider_batch_id, task.provider_output_id = "old-job", "old-output"
    await async_test_db.commit()
    queued = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", queued)
    result = await control_translation_job(async_test_db, sample_scenario.users["admin"], job_id, "retry")
    assert result.dispatched_task_ids == [task.task_id]
    await async_test_db.refresh(task)
    assert task.status == State.READY and task.provider_batch_id is None and task.provider_output_id is None


def test_router_controls_and_permissions(
    client: TestClient, sample_scenario: DatabaseScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": sample_scenario.users["admin"].user_name}, timedelta(minutes=5))
    }
    body = {
        "novelId": str(sample_scenario.novels["novel_1"].novel_id),
        "config": {"batchSize": 10},
        "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}],
    }
    assert client.post("/translation-jobs", json=body).status_code == 401
    created = client.post("/translation-jobs", json=body, headers=headers)
    assert created.status_code == 201, created.text
    job_id = created.json()["jobId"]
    read = client.get(f"/translation-jobs/{job_id}", headers=headers)
    assert read.status_code == 200, read.text
    batch_id = read.json()["batches"][0]["batchId"]
    task_id = read.json()["tasks"][0]["taskId"]
    queued = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", queued)
    start = client.post(f"/translation-jobs/{job_id}/start", headers=headers)
    assert start.status_code == 200 and start.json()["dispatchedTaskIds"] == [task_id]
    for suffix in ("cancel-all", f"batches/{batch_id}/cancel"):
        response = client.post(f"/translation-jobs/{job_id}/{suffix}", headers=headers)
        assert response.status_code == 200 and response.json()["affectedBatchIds"] == [batch_id]
    assert client.post(f"/translation-jobs/{job_id}/resume-all", headers=headers).json()["dispatchedTaskIds"] == []
    for suffix in (f"batches/{batch_id}/retry", "retry-all"):
        response = client.post(f"/translation-jobs/{job_id}/{suffix}", headers=headers)
        assert response.status_code == 200 and response.json()["dispatchedTaskIds"] == [task_id]
    assert client.post(f"/translation-jobs/{job_id}/batches/{uuid4()}/cancel", headers=headers).status_code == 404
    viewer_headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": sample_scenario.users["user"].user_name}, timedelta(minutes=5))
    }
    assert client.post(f"/translation-jobs/{job_id}/cancel-all", headers=viewer_headers).status_code == 404


@pytest.mark.parametrize("operation", ["start", "resume", "retry"])
async def test_control_does_not_overwrite_concurrent_worker_claim(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    operation: Control,
) -> None:
    # A control snapshot can precede a worker claim's commit. The UPDATE must
    # recheck ownership after waiting, so the worker keeps its lease and work.
    # Start only dispatches a batch's first stage, which is the loader.
    starting = operation == "start"
    job_id, (task, *_) = await make_job(async_test_db, sample_scenario, loaded=not starting)
    task_id, token = task.task_id, uuid4()
    user = sample_scenario.users["admin"]
    queued = AsyncMock()
    step, claimed = ("load_inputs.load", State.FINALIZING) if starting else ("translate.prepare", State.PREPARING)
    monkeypatch.setattr(step_task(f"src.translations.actions.{step}"), "kiq", queued)
    await async_test_db.execute(
        update(TranslationTask)
        .where(TranslationTask.task_id == task_id)
        .values(
            status=claimed,
            claim_token=token,
            claim_expires_at=func.clock_timestamp() + timedelta(minutes=5),
        )
    )
    backend_pids: list[int] = []

    async def control():
        async with testing_async_session_local() as db:
            backend_pids.append(await db.scalar(select(func.pg_backend_pid())))
            return await control_translation_job(db, user, job_id, operation)

    controlling = asyncio.create_task(control())
    try:
        async with asyncio.timeout(5):
            while not backend_pids:
                await asyncio.sleep(0.01)
            blocked = select(func.cardinality(func.pg_blocking_pids(backend_pids[0])) > 0)
            while not await async_test_db.scalar(blocked):
                await asyncio.sleep(0.01)
        await async_test_db.commit()
    finally:
        await async_test_db.rollback()
    result = await asyncio.wait_for(controlling, 5)
    assert result.dispatched_task_ids == []
    await async_test_db.refresh(task)
    assert task.status == claimed and task.claim_token == token
    queued.assert_not_called()


@pytest.mark.parametrize("operation", ["resume", "retry"])
async def test_recovery_schedules_poll_at_persisted_deadline(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
    operation: Control,
) -> None:
    # Job controls provide recovery after lost queue delivery; the replacement
    # must survive until the deadline without bypassing the polling interval.
    job_id, (task, _) = await make_job(async_test_db, sample_scenario)
    task.status = State.PROCESSING
    task.provider_batch_id = "provider-job"
    deadline = await async_test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=1)
    task.next_poll_at = deadline
    await async_test_db.commit()
    queued = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.poll"), "schedule_by_time", queued)
    for _ in range(2):
        result = await control_translation_job(async_test_db, sample_scenario.users["admin"], job_id, operation)
        assert result.dispatched_task_ids == [task.task_id]
        # The remaining duration is added to the dispatcher's clock, never the database
        # deadline itself: the scheduler releases the message against its own clock.
        (_, when, scheduled_id), _ = queued.call_args
        assert scheduled_id == str(task.task_id)
        assert timedelta(0) < when - datetime.now(UTC) <= timedelta(seconds=60)
        await async_test_db.refresh(task)
        assert task.next_poll_at == deadline

    # If retry has to rebuild input, that old provider's deadline is irrelevant.
    task.provider_batch_id = None
    await async_test_db.commit()
    prepare = AsyncMock()
    monkeypatch.setattr(step_task("src.translations.actions.translate.prepare"), "kiq", prepare)
    await control_translation_job(async_test_db, sample_scenario.users["admin"], job_id, "retry")
    await async_test_db.refresh(task)
    assert task.status == State.READY and task.next_poll_at is None
    prepare.assert_called_once_with(str(task.task_id))
