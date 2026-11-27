from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.novels.constants import NovelType, Visibility
from src.novels.models import Novel, SourceWork
from src.translations.models import TranslationBatch, TranslationJob, TranslationStage, TranslationTask
from src.translations.tasks.claims import (
    POLL_GATE_SLACK,
    TranslationClaimLostError,
    claim_task,
    fail_claim,
    finish_claim,
)
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


async def acquire(db: AsyncSession, task_id: UUID, token: UUID) -> bool:
    return await claim_task(db, task_id, token, expect=State.READY, during=State.PREPARING, duration=DURATION)


@pytest.mark.parametrize(("until_deadline", "claimable"), [(POLL_GATE_SLACK / 2, True), (POLL_GATE_SLACK * 2, False)])
async def test_poll_gate_admits_slightly_early_message_but_not_a_duplicate(
    task_id: UUID,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    until_deadline: timedelta,
    claimable: bool,
) -> None:
    # Worker clocks can disagree, so a message may arrive before its deadline.
    # Admitting it within the slack window keeps the polling chain alive: a lost
    # claim returns without rescheduling. A real duplicate is far too early to
    # pass, so it still loses and the chain cannot multiply.
    async with testing_async_session_local.begin() as db:
        await db.execute(
            update(TranslationTask)
            .where(TranslationTask.task_id == task_id)
            .values(next_poll_at=func.clock_timestamp() + until_deadline)
        )
    async with testing_async_session_local.begin() as db:
        assert await acquire(db, task_id, uuid4()) is claimable


async def expire(db: AsyncSession, task_id: UUID) -> None:
    await db.execute(
        update(TranslationTask)
        .where(TranslationTask.task_id == task_id)
        .values(claim_expires_at=func.clock_timestamp() - timedelta(seconds=1))
    )


async def test_live_claim_excludes_other_worker(
    task_id: UUID, testing_async_session_local: async_sessionmaker[AsyncSession]
) -> None:
    async with testing_async_session_local.begin() as db:
        assert await acquire(db, task_id, uuid4())
    async with testing_async_session_local.begin() as db:
        assert not await acquire(db, task_id, uuid4())


@pytest.mark.parametrize("replace", [False, True])
async def test_stale_callback_writes_roll_back(
    task_id: UUID,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    replace: bool,
) -> None:
    token, replacement = uuid4(), uuid4()
    async with testing_async_session_local.begin() as db:
        assert await acquire(db, task_id, token)
    async with testing_async_session_local() as stale:
        task = await stale.get(TranslationTask, task_id)
        assert task is not None
        stale.expunge(task)
        task.provider_batch_id = "must not commit"
        # The stale transaction began before expiry; completion must use wall-clock time.
        async with testing_async_session_local.begin() as db:
            await expire(db, task_id)
            if replace:
                assert await acquire(db, task_id, replacement)
        with pytest.raises(TranslationClaimLostError):
            await finish_claim(stale, task, token, during=State.PREPARING, finish=State.PREPARED)
        await stale.rollback()
    async with testing_async_session_local.begin() as db:
        assert not await fail_claim(db, task_id, token, during=State.PREPARING, error="stale failure")
        task = await db.get(TranslationTask, task_id)
        assert task is not None
        assert task.provider_batch_id is None and task.failed_at is None
        assert task.claim_token == (replacement if replace else token)


async def test_complete_claim_commits_callback_fields_and_releases(
    task_id: UUID, testing_async_session_local: async_sessionmaker[AsyncSession]
) -> None:
    token = uuid4()
    async with testing_async_session_local.begin() as db:
        assert await acquire(db, task_id, token)
    async with testing_async_session_local.begin() as db:
        task = await db.get(TranslationTask, task_id)
        assert task is not None
        db.expunge(task)
        task.provider_batch_id = "provider-job"
        await finish_claim(db, task, token, during=State.PREPARING, finish=State.PREPARED)
    async with testing_async_session_local.begin() as db:
        task = await db.get(TranslationTask, task_id)
        assert task is not None
        assert task.status == State.PREPARED and task.provider_batch_id == "provider-job"
        assert task.claim_token is None and task.claim_expires_at is None
        assert not await acquire(db, task_id, uuid4())


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
