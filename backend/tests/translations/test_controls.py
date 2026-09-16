from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic, sleep
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.auth.utils import create_access_token
from src.files.models import StoredFile
from src.translations.actions.registry import ACTION_CALLBACKS, last_step
from src.translations.celery_app import app
from src.translations.models import TranslationBatch, TranslationStage, TranslationTask
from src.translations.schemas import TranslationJobCreate
from src.translations.service import Control, TranslationNotFoundError, control_translation_job, create_translation_job
from src.translations.tasks.claims import TranslationClaimLostError, finish_claim, publish_initial_file
from src.translations.types import TranslationTaskStatus as State
from test_support.test_data.scenarios import DatabaseScenario


def make_job(db: Session, scenario: DatabaseScenario) -> tuple[UUID, list[TranslationTask]]:
    job_id = create_translation_job(
        db,
        scenario.users["admin"],
        TranslationJobCreate.model_validate(
            {
                "novel_id": scenario.novels["novel_1"].novel_id,
                "config": {"batch_size": 10},
                "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}] * 2,
            }
        ),
    )
    tasks = list(
        db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationStage.job_id == job_id)
            .order_by(TranslationStage.stage_num)
        )
    )
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
    for action in ("translate", "translate_with_memories", "prune_memories"):
        step = last_step(action, state)
        assert step is not None and step.expect == expected
    combine = last_step("combine_chapter", State.FINALIZING)
    assert combine is not None and combine.expect == State.READY
    assert last_step("translate", State.COMPLETE) is None


def test_cancel_fences_worker_and_retry_preserves_provider_output(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, following) = make_job(test_db, sample_scenario)
    user = sample_scenario.users["admin"]
    token = uuid4()
    current.status, current.provider_batch_id, current.provider_output_id = State.FINALIZING, "provider", "output"
    current.claim_token = token
    current.claim_expires_at = test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=5)
    test_db.commit()
    # The operator can cancel a live worker. Its token must no longer commit.
    cancelled = control_translation_job(test_db, user, job_id, "cancel", batch_id=current.batch_id)
    assert cancelled.affected_batch_ids == [current.batch_id]
    test_db.refresh(current)
    test_db.refresh(following)
    assert current.claim_token is None and current.status == State.FINALIZING and current.failed_at is not None
    assert following.failed_at is not None and following.status == State.WAITING
    with testing_session_local.begin() as db, pytest.raises(TranslationClaimLostError):
        finish_claim(db, current.task_id, token, during=State.FINALIZING, finish=State.COMPLETE)
    assert not control_translation_job(test_db, user, job_id, "resume").affected_batch_ids

    def observe(*args: object, **kwargs: object) -> None:
        with testing_session_local() as db:
            task = db.get(TranslationTask, current.task_id)
            next_task = db.get(TranslationTask, following.task_id)
            assert task is not None and task.status == State.PROCESSED and task.failed_at is None
            assert task.provider_output_id == "output"
            assert next_task is not None and next_task.failed_at is None and next_task.status == State.WAITING

    queued = Mock(side_effect=observe)
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.finalize"], "apply_async", queued)
    retried = control_translation_job(test_db, user, job_id, "retry", batch_id=current.batch_id)
    assert retried.dispatched_task_ids == [current.task_id]
    queued.assert_called_once_with((current.task_id,))


def test_resume_skips_live_claim_then_resumes_expired_poll_and_reports_broker_failure(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, _) = make_job(test_db, sample_scenario)
    current.status, current.provider_batch_id = State.PROCESSING, "provider"
    current.claim_token = uuid4()
    current.claim_expires_at = test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=5)
    test_db.commit()
    queued = Mock(side_effect=ConnectionError("broker unavailable"))
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.poll"], "apply_async", queued)
    user = sample_scenario.users["admin"]
    for operation in ("resume", "retry"):
        assert not control_translation_job(test_db, user, job_id, operation).affected_batch_ids
    queued.assert_not_called()
    current.claim_expires_at = test_db.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)
    test_db.commit()
    result = control_translation_job(test_db, user, job_id, "resume")
    assert result.dispatch_failed_task_ids == [current.task_id] and not result.dispatched_task_ids
    test_db.refresh(current)
    assert current.claim_token is None and current.failed_at is None and current.status == State.PROCESSING
    queued.side_effect = None
    assert control_translation_job(test_db, user, job_id, "resume").dispatched_task_ids == [current.task_id]


def test_cancel_fences_inflight_exitpoint(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (current, following) = make_job(test_db, sample_scenario)
    current.status = State.COMPLETE
    test_db.commit()
    current_id = current.task_id
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", queued)
    test_db.execute(
        update(TranslationTask).where(TranslationTask.task_id == following.task_id).values(error="pending cancel")
    )
    entered = Event()
    engine = testing_session_local.kw["bind"]

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE translation_tasks") and parameters.get("status") == State.READY:
            entered.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(ACTION_CALLBACKS["translate"].exitpoint, current_id)
            try:
                assert entered.wait(5)
                control_translation_job(test_db, sample_scenario.users["admin"], job_id, "cancel")
            finally:
                test_db.rollback()  # Release the lock even if the test fails.
            worker.result(timeout=5)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    test_db.refresh(following)
    assert following.status == State.WAITING and following.failed_at is not None
    queued.assert_not_called()


def test_controls_isolate_batches_and_resume_later_stage(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (first, second) = make_job(test_db, sample_scenario)
    other_batch = TranslationBatch(job_id=job_id, batch_num=1)
    test_db.add(other_batch)
    test_db.flush()
    completed = TranslationTask(batch_id=other_batch.batch_id, stage_id=first.stage_id, status=State.COMPLETE)
    waiting = TranslationTask(batch_id=other_batch.batch_id, stage_id=second.stage_id, status=State.WAITING)
    test_db.add_all([completed, waiting])
    test_db.commit()
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", queued)
    user = sample_scenario.users["admin"]
    control_translation_job(test_db, user, job_id, "cancel", batch_id=first.batch_id)
    resumed = control_translation_job(test_db, user, job_id, "resume")
    assert resumed.dispatched_task_ids == [waiting.task_id]
    test_db.refresh(waiting)
    assert waiting.status == State.READY and waiting.failed_at is None
    test_db.refresh(first)
    assert first.failed_at is not None
    waiting.status = State.COMPLETE
    test_db.commit()
    retried = control_translation_job(test_db, user, job_id, "retry")
    assert retried.dispatched_task_ids == [first.task_id]
    assert retried.affected_batch_ids == [first.batch_id]


def test_retry_preparation_discards_stale_provider_ids(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, (task, _) = make_job(test_db, sample_scenario)
    task.status = State.PREPARING
    task.failed_at = test_db.scalar(select(func.clock_timestamp()))
    task.provider_batch_id, task.provider_output_id = "old-job", "old-output"
    test_db.commit()
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", queued)
    result = control_translation_job(test_db, sample_scenario.users["admin"], job_id, "retry")
    assert result.dispatched_task_ids == [task.task_id]
    test_db.refresh(task)
    assert task.status == State.READY and task.provider_batch_id is None and task.provider_output_id is None


def test_router_controls_and_permissions(
    client: TestClient, test_db: Session, sample_scenario: DatabaseScenario, monkeypatch: pytest.MonkeyPatch
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
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", queued)
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
    with pytest.raises(TranslationNotFoundError):
        control_translation_job(test_db, sample_scenario.users["user"], UUID(job_id), "cancel")


def test_cancel_during_snapshot_publication_rolls_back_worker(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
) -> None:
    # Controls must cancel without waiting for a worker's batch artifact write;
    # the worker must then roll that artifact back when completion loses its claim.
    job_id, (task, _) = make_job(test_db, sample_scenario)
    token = uuid4()
    task.status = State.PREPARING
    task.claim_token = token
    task.claim_expires_at = test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=5)
    file = StoredFile(
        storage_name="test",
        bucket="test",
        object_key=str(uuid4()),
        content_type="application/jsonl",
        byte_size=0,
        sha256="0" * 64,
    )
    test_db.add(file)
    test_db.commit()
    task_id, batch_id, file_id = task.task_id, task.batch_id, file.file_id
    published, cancelled = Event(), Event()

    def worker():
        with testing_session_local() as db:
            try:
                publish_initial_file(db, task_id, token, file_id)
                published.set()
                assert cancelled.wait(10)
                with pytest.raises(TranslationClaimLostError):
                    finish_claim(db, task_id, token, during=State.PREPARING, finish=State.PREPARED)
            finally:
                db.rollback()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            assert published.wait(5)
            # Bound a regression's failure rather than hanging on the old batch lock.
            test_db.execute(select(func.set_config("lock_timeout", "2000", True)))
            result = control_translation_job(test_db, sample_scenario.users["admin"], job_id, "cancel")
            assert result.affected_batch_ids == [batch_id]
        finally:
            cancelled.set()
        future.result(timeout=5)
    test_db.refresh(task)
    assert task.failed_at is not None and task.claim_token is None
    assert test_db.scalar(select(TranslationBatch.initial_file_id).where(TranslationBatch.batch_id == batch_id)) is None


@pytest.mark.parametrize("operation", ["start", "resume", "retry"])
def test_control_does_not_overwrite_concurrent_worker_claim(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    operation: Control,
) -> None:
    # A control snapshot can precede a worker claim's commit. The UPDATE must
    # recheck ownership after waiting, so the worker keeps its lease and work.
    job_id, (task, _) = make_job(test_db, sample_scenario)
    task_id, token = task.task_id, uuid4()
    user = sample_scenario.users["admin"]
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", queued)
    test_db.execute(
        update(TranslationTask)
        .where(TranslationTask.task_id == task_id)
        .values(
            status=State.PREPARING,
            claim_token=token,
            claim_expires_at=func.clock_timestamp() + timedelta(minutes=5),
        )
    )
    started = Event()
    backend_pids: list[int] = []

    def control():
        with testing_session_local() as db:
            backend_pids.append(db.scalar(select(func.pg_backend_pid())))
            started.set()
            return control_translation_job(db, user, job_id, operation)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(control)
        try:
            assert started.wait(5)
            deadline = monotonic() + 5
            while not test_db.scalar(select(func.cardinality(func.pg_blocking_pids(backend_pids[0])) > 0)):
                assert monotonic() < deadline, "Control did not reach the contested UPDATE"
                sleep(0.01)
            test_db.commit()
        finally:
            test_db.rollback()
        result = future.result(timeout=5)
    assert result.dispatched_task_ids == []
    test_db.refresh(task)
    assert task.status == State.PREPARING and task.claim_token == token
    queued.assert_not_called()


@pytest.mark.parametrize("operation", ["resume", "retry"])
def test_recovery_schedules_poll_at_persisted_deadline(
    test_db: Session,
    sample_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
    operation: Control,
) -> None:
    # Job controls provide recovery after lost queue delivery; the replacement
    # must survive until the deadline without bypassing the polling interval.
    job_id, (task, _) = make_job(test_db, sample_scenario)
    task.status = State.PROCESSING
    task.provider_batch_id = "provider-job"
    deadline = test_db.scalar(select(func.clock_timestamp())) + timedelta(minutes=1)
    task.next_poll_at = deadline
    test_db.commit()
    queued = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.poll"], "apply_async", queued)
    for _ in range(2):
        result = control_translation_job(test_db, sample_scenario.users["admin"], job_id, operation)
        assert result.dispatched_task_ids == [task.task_id]
        # A duration, never the deadline itself: the consuming worker releases
        # the message against its own clock, not the database's.
        args, kwargs = queued.call_args
        assert args == ((task.task_id,),)
        assert list(kwargs) == ["countdown"] and 0 < kwargs["countdown"] <= 60
        test_db.refresh(task)
        assert task.next_poll_at == deadline

    # If retry has to rebuild input, that old provider's deadline is irrelevant.
    task.provider_batch_id = None
    test_db.commit()
    prepare = Mock()
    monkeypatch.setattr(app.tasks["src.translations.actions.translate.prepare"], "apply_async", prepare)
    control_translation_job(test_db, sample_scenario.users["admin"], job_id, "retry")
    test_db.refresh(task)
    assert task.status == State.READY and task.next_poll_at is None
    prepare.assert_called_once_with((task.task_id,))
