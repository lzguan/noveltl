"""Bounded viewer reads; aggregate task progress in SQL, never load chapter rows."""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.novels.models import Novel
from src.novels.permissions import novel_mod_access_select
from src.translations.models import TranslationBatch, TranslationJob, TranslationStage, TranslationTask
from src.translations.schemas import (
    TranslationBatchDetail,
    TranslationBatchPage,
    TranslationJobPage,
    TranslationJobSummary,
    TranslationProgress,
    TranslationStageRead,
    TranslationTaskRead,
)
from src.translations.service import TranslationNotFoundError, _job
from src.translations.types import TranslationTaskStatus as State


def _summaries(db: Session, jobs: list[TranslationJob]) -> list[TranslationJobSummary]:
    if not jobs:
        return []
    ids = [job.job_id for job in jobs]
    task = TranslationTask
    unfinished = task.status != State.COMPLETE
    failed = and_(unfinished, task.failed_at.is_not(None))
    live = and_(unfinished, task.claim_token.is_not(None), task.claim_expires_at > func.now())
    batches = (
        select(
            TranslationBatch.job_id,
            func.count(task.task_id).label("total"),
            func.count(task.task_id).filter(task.status == State.COMPLETE).label("completed"),
            func.count(task.task_id).filter(failed).label("failed"),
            func.count(task.task_id).filter(and_(failed, task.error == "Cancelled by user")).label("cancelled"),
            func.count(task.task_id).filter(live).label("live"),
            func.count(task.task_id)
            .filter(and_(unfinished, or_(live, task.status == State.PROCESSING)))
            .label("active"),
            func.count(task.task_id)
            .filter(and_(TranslationStage.stage_num == 0, task.status == State.READY))
            .label("ready"),
        )
        .select_from(TranslationBatch)
        .outerjoin(task, task.batch_id == TranslationBatch.batch_id)
        .outerjoin(TranslationStage, TranslationStage.stage_id == task.stage_id)
        .where(TranslationBatch.job_id.in_(ids))
        .group_by(TranslationBatch.job_id, TranslationBatch.batch_id)
        .subquery()
    )
    b = batches.c
    incomplete = b.completed < b.total
    recoverable = and_(incomplete, b.live == 0)
    query = select(
        b.job_id,
        func.sum(b.total).label("total_tasks"),
        func.sum(b.completed).label("completed_tasks"),
        func.count().label("total_batches"),
        func.count().filter(and_(b.total > 0, b.completed == b.total)).label("completed_batches"),
        func.count().filter(b.failed > b.cancelled).label("failed_batches"),
        func.count().filter(and_(b.failed > 0, b.failed == b.cancelled)).label("cancelled_batches"),
        func.count().filter(and_(b.failed == 0, b.active > 0)).label("active_batches"),
        func.count().filter(and_(recoverable, b.failed == 0, b.ready > 0)).label("startable_batches"),
        func.count().filter(and_(recoverable, b.failed == 0)).label("resumable_batches"),
        func.count().filter(recoverable).label("retryable_batches"),
    ).group_by(b.job_id)
    progress = {row["job_id"]: TranslationProgress.model_validate(row) for row in db.execute(query).mappings()}
    stages: dict[UUID, list[TranslationStageRead]] = {job_id: [] for job_id in ids}
    for stage in db.scalars(
        select(TranslationStage).where(TranslationStage.job_id.in_(ids)).order_by(TranslationStage.stage_num)
    ):
        stages[stage.job_id].append(TranslationStageRead.model_validate(stage))
    return [
        TranslationJobSummary(
            job_id=job.job_id,
            config=job.config,
            stages=stages[job.job_id],
            progress=progress.get(job.job_id, TranslationProgress()),
        )
        for job in jobs
    ]


def list_translation_jobs(db: Session, user: User, novel_id: UUID, *, offset: int, limit: int) -> TranslationJobPage:
    if (
        db.scalar(
            novel_mod_access_select(select(Novel.novel_id).where(Novel.novel_id == novel_id), user, edit_only=True)
        )
        is None
    ):
        raise TranslationNotFoundError("Novel not found")
    scope = TranslationJob.novel_id == novel_id
    total = db.scalar(select(func.count()).select_from(TranslationJob).where(scope)) or 0
    # Jobs currently have no creation timestamp. UUID order is stable, not chronological.
    jobs = list(
        db.scalars(select(TranslationJob).where(scope).order_by(TranslationJob.job_id).offset(offset).limit(limit))
    )
    return TranslationJobPage(items=_summaries(db, jobs), total=total)


def read_translation_batches(db: Session, user: User, job_id: UUID, *, offset: int, limit: int) -> TranslationBatchPage:
    job = _job(db, user, job_id)
    observed_at = db.execute(select(func.now())).scalar_one()
    summary = _summaries(db, [job])[0]
    batches = list(
        db.scalars(
            select(TranslationBatch)
            .where(TranslationBatch.job_id == job_id)
            .order_by(TranslationBatch.batch_num)
            .offset(offset)
            .limit(limit)
        )
    )
    tasks: dict[UUID, list[TranslationTaskRead]] = {batch.batch_id: [] for batch in batches}
    if tasks:
        for task in db.scalars(
            select(TranslationTask)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(TranslationTask.batch_id.in_(tasks))
            .order_by(TranslationStage.stage_num)
        ):
            tasks[task.batch_id].append(TranslationTaskRead.model_validate(task))
    return TranslationBatchPage(
        job=summary,
        total=summary.progress.total_batches,
        observed_at=observed_at,
        items=[
            TranslationBatchDetail(
                batch_id=batch.batch_id,
                batch_num=batch.batch_num,
                initial_file_id=batch.initial_file_id,
                tasks=tasks[batch.batch_id],
            )
            for batch in batches
        ],
    )
