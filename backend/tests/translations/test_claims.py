from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from celery import Celery
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from src.languages.models import Language
from src.novels.constants import NovelType, Visibility
from src.novels.models import Novel, SourceWork
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.celery_actions import CeleryActionCallbacks
from src.translations.models import TranslationBatch, TranslationJob, TranslationStage, TranslationTask
from src.translations.tasks.claims import TranslationClaimLostError, claim_task, fail_claim, finish_claim, renew_claim
from src.translations.types import TranslationTaskStatus as State

DURATION = timedelta(minutes=5)


@pytest.fixture
def task_id(test_db: Session) -> UUID:
    language = Language(language_name="Chinese", language_code="zh")
    source = SourceWork(source_work_title="Claim test")
    test_db.add_all([language, source])
    test_db.flush()
    novel = Novel(
        novel_title="Claim test",
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()
    job = TranslationJob(novel_id=novel.novel_id, config={})
    test_db.add(job)
    test_db.flush()
    stage = TranslationStage(job_id=job.job_id, stage_num=0, action="translate", config={})
    batch = TranslationBatch(job_id=job.job_id, batch_num=0)
    test_db.add_all([stage, batch])
    test_db.flush()
    task = TranslationTask(stage_id=stage.stage_id, batch_id=batch.batch_id, status=State.READY)
    test_db.add(task)
    test_db.flush()
    result = task.task_id
    test_db.commit()
    return result


def acquire(db: Session, task_id: UUID, token: UUID) -> bool:
    return claim_task(db, task_id, token, expect=State.READY, during=State.PREPARING, duration=DURATION)


def expire(db: Session, task_id: UUID) -> None:
    db.execute(
        update(TranslationTask)
        .where(TranslationTask.task_id == task_id)
        .values(claim_expires_at=func.clock_timestamp() - timedelta(seconds=1))
    )


def test_live_claim_excludes_other_worker_and_can_renew(
    task_id: UUID, testing_session_local: sessionmaker[Session]
) -> None:
    token = uuid4()
    with testing_session_local.begin() as db:
        assert acquire(db, task_id, token)
    with testing_session_local.begin() as db:
        assert not acquire(db, task_id, uuid4())
        assert not renew_claim(db, task_id, uuid4(), during=State.PREPARING, duration=DURATION)
        before = db.scalar(select(TranslationTask.claim_expires_at).where(TranslationTask.task_id == task_id))
        assert renew_claim(db, task_id, token, during=State.PREPARING, duration=DURATION * 2)
        after = db.scalar(select(TranslationTask.claim_expires_at).where(TranslationTask.task_id == task_id))
        assert before is not None and after is not None and after > before


@pytest.mark.parametrize("replace", [False, True])
def test_stale_callback_writes_roll_back(
    task_id: UUID,
    testing_session_local: sessionmaker[Session],
    replace: bool,
) -> None:
    token, replacement = uuid4(), uuid4()
    with testing_session_local.begin() as db:
        assert acquire(db, task_id, token)
    with testing_session_local() as stale:
        task = stale.get(TranslationTask, task_id)
        assert task is not None
        task.provider_batch_id = "must not commit"
        # The stale transaction began before expiry; completion must use wall-clock time.
        with testing_session_local.begin() as db:
            expire(db, task_id)
            assert not renew_claim(db, task_id, token, during=State.PREPARING, duration=DURATION)
            if replace:
                assert acquire(db, task_id, replacement)
        with pytest.raises(TranslationClaimLostError):
            finish_claim(stale, task_id, token, during=State.PREPARING, finish=State.PREPARED)
        stale.rollback()
    with testing_session_local.begin() as db:
        assert not fail_claim(db, task_id, token, during=State.PREPARING, error="stale failure")
        task = db.get(TranslationTask, task_id)
        assert task is not None
        assert task.provider_batch_id is None and task.failed_at is None
        assert task.claim_token == (replacement if replace else token)


def test_complete_claim_commits_callback_fields_and_releases(
    task_id: UUID, testing_session_local: sessionmaker[Session]
) -> None:
    token = uuid4()
    with testing_session_local.begin() as db:
        assert acquire(db, task_id, token)
    with testing_session_local.begin() as db:
        task = db.get(TranslationTask, task_id)
        assert task is not None
        task.provider_batch_id = "provider-job"
        finish_claim(db, task_id, token, during=State.PREPARING, finish=State.PREPARED)
    with testing_session_local.begin() as db:
        task = db.get(TranslationTask, task_id)
        assert task is not None
        assert task.status == State.PREPARED and task.provider_batch_id == "provider-job"
        assert task.claim_token is None and task.claim_expires_at is None
        assert not acquire(db, task_id, uuid4())


def test_wrapper_failure_rolls_back_and_blocks_retry(
    task_id: UUID,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    app = Celery("claim-test", set_as_current=False)
    callbacks = CeleryActionCallbacks(app, {})
    calls = []

    @callbacks.new_func(expect=State.READY, during=State.PREPARING, finish=State.PREPARED)
    def failing(context: ActionTaskContext) -> None:
        calls.append(context.task.task_id)
        context.renew_lease()
        context.task.provider_batch_id = "rolled-back"
        context.db.flush()
        raise ValueError("failed preparation")

    try:
        with pytest.raises(ValueError, match="failed preparation"):
            failing(task_id)
        failing(task_id)
        assert calls == [task_id]
        with testing_session_local() as db:
            task = db.get(TranslationTask, task_id)
            assert task is not None
            assert task.provider_batch_id is None
            assert task.failed_at is not None and task.error == "failed preparation"
            assert task.status == State.PREPARING
            assert task.claim_token is None and task.claim_expires_at is None
    finally:
        app.close()


def test_wrapper_commits_before_running_next_step(
    task_id: UUID,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    app = Celery("claim-sequence-test", set_as_current=False, broker="memory://")
    app.conf.update(task_always_eager=True, task_eager_propagates=True)
    callbacks = CeleryActionCallbacks(app, {})
    calls = []

    @callbacks.new_func(expect=State.READY, during=State.PREPARING, finish=State.PREPARED)
    def first(context: ActionTaskContext) -> None:
        context.task.provider_batch_id = "committed"

    @callbacks.new_func(expect=State.PREPARED, during=State.FINALIZING, finish=State.COMPLETE)
    def second(context: ActionTaskContext) -> None:
        assert context.task.provider_batch_id == "committed"
        calls.append(context.task.task_id)

    try:
        first(task_id)
        first(task_id)
        assert calls == [task_id]
        with testing_session_local() as db:
            task = db.get(TranslationTask, task_id)
            assert task is not None
            assert task.status == State.COMPLETE and task.claim_token is None
    finally:
        app.close()


@pytest.fixture
def next_task_id(task_id: UUID, test_db: Session) -> UUID:
    current = test_db.get(TranslationTask, task_id)
    assert current is not None
    stage = test_db.get(TranslationStage, current.stage_id)
    assert stage is not None
    next_stage = TranslationStage(job_id=stage.job_id, stage_num=1, action="prune_memories", config={})
    test_db.add(next_stage)
    test_db.flush()
    task = TranslationTask(stage_id=next_stage.stage_id, batch_id=current.batch_id, status=State.WAITING)
    test_db.add(task)
    test_db.flush()
    result = task.task_id
    test_db.commit()
    return result


def test_exitpoint_commits_ready_before_dispatch_and_can_retry(
    task_id: UUID,
    next_task_id: UUID,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    app = Celery("exitpoint-test", set_as_current=False)
    calls: list[UUID] = []

    # Replace only the queue boundary; read the committed state in a real new session.
    class NextAction(CeleryActionCallbacks):
        def entrypoint(self, x: UUID) -> None:
            with testing_session_local() as db:
                task = db.get(TranslationTask, x)
                assert task is not None and task.status == State.READY
            calls.append(x)
            if len(calls) == 1:
                raise ConnectionError("broker unavailable")

    callbacks = CeleryActionCallbacks(app, {"prune_memories": NextAction(app, {})})
    try:
        with testing_session_local.begin() as db:
            db.execute(update(TranslationTask).where(TranslationTask.task_id == task_id).values(status=State.COMPLETE))
        with pytest.raises(ConnectionError, match="broker unavailable"):
            callbacks.exitpoint(task_id)
        callbacks.exitpoint(task_id)
        assert calls == [next_task_id, next_task_id]
    finally:
        app.close()


@pytest.mark.parametrize(
    ("current_status", "next_status", "failed"),
    [
        (State.FINALIZING, State.WAITING, False),
        (State.COMPLETE, State.PREPARING, False),
        (State.COMPLETE, State.COMPLETE, False),
        (State.COMPLETE, State.WAITING, True),
    ],
)
def test_exitpoint_does_not_advance_ineligible_tasks(
    task_id: UUID,
    next_task_id: UUID,
    testing_session_local: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    current_status: State,
    next_status: State,
    failed: bool,
) -> None:
    monkeypatch.setattr("src.translations.actions.celery_actions.SessionLocal", testing_session_local)
    app = Celery("exitpoint-ineligible-test", set_as_current=False)
    try:
        with testing_session_local.begin() as db:
            db.execute(update(TranslationTask).where(TranslationTask.task_id == task_id).values(status=current_status))
            db.execute(
                update(TranslationTask)
                .where(TranslationTask.task_id == next_task_id)
                .values(
                    status=next_status,
                    failed_at=func.clock_timestamp() if failed else None,
                )
            )
        # An empty registry also ensures an ineligible task never reaches dispatch.
        CeleryActionCallbacks(app, {}).exitpoint(task_id)
        with testing_session_local() as db:
            task = db.get(TranslationTask, next_task_id)
            assert task is not None and task.status == next_status
            assert (task.failed_at is not None) == failed
    finally:
        app.close()
