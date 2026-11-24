import uuid
from datetime import timedelta
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from src.translations.actions.actions import ActionTaskContext, PollCallback
from src.translations.models import TranslationStage, TranslationTask
from src.translations.tasks.claims import claim_task, fail_claim, finish_claim
from src.translations.types import TranslationTaskStatus

type StepOutcome = Literal["unclaimed", "advanced", "pending"]


async def run_claimed_step(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: uuid.UUID,
    f: PollCallback,
    *,
    expect: TranslationTaskStatus,
    during: TranslationTaskStatus,
    finish: TranslationTaskStatus,
    duration: timedelta,
    interval_seconds: int,
) -> StepOutcome:
    token = uuid.uuid4()
    async with session_factory.begin() as session:
        if not await claim_task(session, task_id, token, expect=expect, during=during, duration=duration):
            return "unclaimed"

    try:
        async with session_factory() as session:
            task = (
                await session.execute(select(TranslationTask).where(TranslationTask.task_id == task_id))
            ).scalar_one()
            await session.commit()
            done = await f(ActionTaskContext(db=session, task=task))
            await finish_claim(
                session,
                task_id,
                token,
                during=during,
                finish=finish if done else expect,
                poll_interval=timedelta(seconds=interval_seconds) if not done else None,
            )
            await session.commit()
    except Exception as error:
        async with session_factory.begin() as session:
            await fail_claim(session, task_id, token, during=during, error=str(error))
        raise
    return "advanced" if done else "pending"


async def ready_next_task(
    session_factory: async_sessionmaker[AsyncSession], task_id: uuid.UUID
) -> tuple[uuid.UUID, str] | None:
    async with session_factory.begin() as session:
        cur_task_q = (
            select(TranslationTask.batch_id, TranslationStage.job_id, TranslationStage.stage_num)
            .where(
                TranslationTask.task_id == task_id,
                TranslationTask.status == TranslationTaskStatus.COMPLETE,
                TranslationTask.failed_at.is_(None),
            )
            .join(TranslationStage, TranslationTask.stage_id == TranslationStage.stage_id)
            .subquery()
        )
        tsa = aliased(TranslationStage)
        tta = aliased(TranslationTask)
        next_task = (
            await session.execute(
                select(tta.task_id, tsa.action)
                .select_from(cur_task_q)
                .join(tsa, (tsa.job_id == cur_task_q.c.job_id) & (tsa.stage_num == cur_task_q.c.stage_num + 1))
                .join(tta, (tta.batch_id == cur_task_q.c.batch_id) & (tta.stage_id == tsa.stage_id))
            )
        ).one_or_none()
        if next_task is None:
            return None
        next_task_id, next_action = next_task
        ready_task_id = await session.scalar(
            update(TranslationTask)
            .where(
                TranslationTask.task_id == next_task_id,
                TranslationTask.status.in_((TranslationTaskStatus.WAITING, TranslationTaskStatus.READY)),
                TranslationTask.failed_at.is_(None),
                TranslationTask.claim_token.is_(None),
            )
            .values(status=TranslationTaskStatus.READY)
            .returning(TranslationTask.task_id)
        )
        if ready_task_id is None:
            return None
    return next_task_id, next_action
