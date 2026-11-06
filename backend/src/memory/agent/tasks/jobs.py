import uuid
from datetime import timedelta
from typing import Literal

from sqlalchemy import Select, and_, func, insert, literal, or_, select, tuple_, union_all, update
from sqlalchemy.orm import Session

from src.memory.agent.config import (
    JobParams,
    RecordMemoriesStageConfig,
    StageConfig,
    SummarizeConventionsStageConfig,
    TranslateTermsStageConfig,
    resolve_stages,
)
from src.memory.agent.tasks.schedule import TaskSchedule
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus
from src.novels.models import Chapter


def _owns_job_claim(memory_job_id: uuid.UUID, claim_token: uuid.UUID):
    return (
        select(MemoryJob.memory_job_id)
        .where(
            MemoryJob.memory_job_id == memory_job_id,
            MemoryJob.claim_token == claim_token,
            MemoryJob.claim_expires_at >= func.now(),
        )
        .exists()
    )


def claim_job(
    db: Session,
    memory_job_id: uuid.UUID,
    claim_token: uuid.UUID,
    claim_duration: timedelta,
) -> MemoryJob | None:
    """Claim a job that has pending or abandoned processing work."""
    if claim_duration <= timedelta(0):
        raise ValueError("claim_duration must be positive")

    has_pending_task = (
        select(MemoryChapterTask.memory_job_id)
        .where(
            MemoryChapterTask.memory_job_id == MemoryJob.memory_job_id,
            MemoryChapterTask.task_status == JobStatus.PENDING,
        )
        .exists()
    )
    has_runnable_task = (
        select(MemoryChapterTask.memory_job_id)
        .where(
            MemoryChapterTask.memory_job_id == MemoryJob.memory_job_id,
            MemoryChapterTask.task_status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
        )
        .exists()
    )
    claim_stmt = (
        update(MemoryJob)
        .where(
            MemoryJob.memory_job_id == memory_job_id,
            or_(
                and_(MemoryJob.claim_token.is_(None), has_pending_task),
                and_(MemoryJob.claim_expires_at < func.now(), has_runnable_task),
            ),
        )
        .values(
            claim_token=claim_token,
            claim_expires_at=func.now() + claim_duration,
        )
        .returning(MemoryJob)
    )

    try:
        job = db.execute(claim_stmt).scalar_one_or_none()
        if job is not None:
            # A successfully replaced lease is the ownership boundary. Any
            # processing task predates this token and is safe to retry.
            db.execute(
                update(MemoryChapterTask)
                .where(
                    MemoryChapterTask.memory_job_id == memory_job_id,
                    MemoryChapterTask.task_status == JobStatus.PROCESSING,
                )
                .values(task_status=JobStatus.PENDING)
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return job


def release_job(
    db: Session,
    memory_job_id: uuid.UUID,
    claim_token: uuid.UUID,
) -> bool:
    """Release a matching claim and commit the current chapter transaction."""
    release_stmt = (
        update(MemoryJob)
        .where(
            MemoryJob.memory_job_id == memory_job_id,
            MemoryJob.claim_token == claim_token,
        )
        .values(claim_token=None, claim_expires_at=None)
        .returning(MemoryJob.memory_job_id)
    )

    try:
        released_job_id = db.scalar(release_stmt)
        if released_job_id is None:
            db.rollback()
            return False
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def abort_job(db: Session, memory_job_id: uuid.UUID) -> bool:
    """Fail active tasks and clear the job claim, invalidating the current worker."""
    abort_stmt = (
        update(MemoryJob)
        .where(MemoryJob.memory_job_id == memory_job_id)
        .values(claim_token=None, claim_expires_at=None)
        .returning(MemoryJob.memory_job_id)
    )

    try:
        aborted_job_id = db.scalar(abort_stmt)
        if aborted_job_id is None:
            db.rollback()
            return False
        db.execute(
            update(MemoryChapterTask)
            .where(
                MemoryChapterTask.memory_job_id == memory_job_id,
                MemoryChapterTask.task_status == JobStatus.PROCESSING,
            )
            .values(task_status=JobStatus.FAILED)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def refresh_job(
    db: Session,
    memory_job_id: uuid.UUID,
    claim_token: uuid.UUID,
    claim_duration: timedelta,
) -> bool:
    """Extend an unexpired job claim owned by the caller."""
    if claim_duration <= timedelta(0):
        raise ValueError("claim_duration must be positive")

    refresh_stmt = (
        update(MemoryJob)
        .where(
            MemoryJob.memory_job_id == memory_job_id,
            MemoryJob.claim_token == claim_token,
            MemoryJob.claim_expires_at >= func.now(),
        )
        .values(claim_expires_at=func.now() + claim_duration)
        .returning(MemoryJob.memory_job_id)
    )

    try:
        refreshed_job_id = db.scalar(refresh_stmt)
        if refreshed_job_id is None:
            db.rollback()
            return False
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def stage_task_chapters(stage: StageConfig, chapters: Select[uuid.UUID]) -> Select[uuid.UUID]:
    """Narrow a job's chapter range to the chapters that get a task for this stage."""
    match stage:
        case RecordMemoriesStageConfig() | TranslateTermsStageConfig():
            return chapters
        case SummarizeConventionsStageConfig():
            # One range-wide task on the last chapter. Stage barriers then order it
            # after every lower-stage task and before every higher-stage task.
            return chapters.order_by(Chapter.chapter_num.desc()).limit(1)


def make_job(
    db: Session,
    memory_group_id: uuid.UUID,
    start_chapter_num: int | None,
    end_chapter_num: int | None,
    params: JobParams,
) -> uuid.UUID:
    """
    Create a new job in the database.

    Args:
        db: The database session.
        memory_group_id: The ID of the memory group.
        start_chapter_num: The starting chapter number (inclusive).
        end_chapter_num: The ending chapter number (exclusive).
        params: The job parameters.

    Returns:
        The ID of the new job.
    """
    memory_job_id = uuid.uuid4()
    job_stmt = insert(MemoryJob).values(
        memory_job_id=memory_job_id,
        memory_group_id=memory_group_id,
        job_params=params.model_dump(mode="json"),
    )

    chapter_query = (
        select(Chapter.chapter_id)
        .join(MemoryGroup, MemoryGroup.novel_id == Chapter.novel_id)
        .where(MemoryGroup.memory_group_id == memory_group_id)
    )
    if start_chapter_num is not None:
        chapter_query = chapter_query.where(Chapter.chapter_num >= start_chapter_num)
    if end_chapter_num is not None:
        chapter_query = chapter_query.where(Chapter.chapter_num < end_chapter_num)

    task_rows = []
    for stage_num, stage in enumerate(resolve_stages(params)):
        stage_chapters = stage_task_chapters(stage, chapter_query).subquery()
        task_rows.append(
            select(
                literal(memory_job_id).label("memory_job_id"),
                stage_chapters.c.chapter_id,
                literal(stage_num).label("stage_num"),
            )
        )
    tasks = union_all(*task_rows).subquery()

    try:
        db.execute(job_stmt)
        db.execute(
            insert(MemoryChapterTask).from_select(
                [
                    MemoryChapterTask.memory_job_id,
                    MemoryChapterTask.chapter_id,
                    MemoryChapterTask.stage_num,
                ],
                select(tasks.c.memory_job_id, tasks.c.chapter_id, tasks.c.stage_num),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return memory_job_id


def claim_next_task(
    db: Session,
    memory_job_id: uuid.UUID,
    claim_token: uuid.UUID,
    schedule: TaskSchedule,
) -> MemoryChapterTask | None:
    """
    Mark and return the next pending task while the caller owns the job claim.

    ``claim_job`` returns abandoned processing work to pending when ownership
    changes, so task claiming remains idempotent for the current worker.

    Args:
        db: The database session.
        memory_job_id: The ID of the job.
        claim_token: The token proving ownership of the job claim.
        schedule: Decides which task is next.
    Returns:
        The claimed task, or None if there is no pending task or the job claim
        is not currently owned by the caller.
    """
    next_task = schedule.next_unfinished(memory_job_id).where(_owns_job_claim(memory_job_id, claim_token))
    claim_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            tuple_(MemoryChapterTask.chapter_id, MemoryChapterTask.stage_num).in_(next_task),
            MemoryChapterTask.task_status == JobStatus.PENDING,
        )
        .values(
            task_status=JobStatus.PROCESSING,
            attempt_count=MemoryChapterTask.attempt_count + 1,
        )
        .returning(MemoryChapterTask)
    )

    try:
        task = db.execute(claim_stmt).scalar_one_or_none()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return task


def claim_task(
    db: Session,
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
    claim_token: uuid.UUID,
    schedule: TaskSchedule,
    stage_num: int = 0,
) -> MemoryChapterTask | None:
    """Mark a specified pending task as processing while owning the job claim."""
    claim_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
            MemoryChapterTask.stage_num == stage_num,
            MemoryChapterTask.task_status == JobStatus.PENDING,
            _owns_job_claim(memory_job_id, claim_token),
            ~schedule.unfinished_prerequisites(memory_job_id, chapter_id, stage_num),
        )
        .values(
            task_status=JobStatus.PROCESSING,
            attempt_count=MemoryChapterTask.attempt_count + 1,
        )
        .returning(MemoryChapterTask)
    )

    try:
        task = db.execute(claim_stmt).scalar_one_or_none()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return task


def release_task(
    db: Session,
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
    claim_token: uuid.UUID,
    task_status: Literal[JobStatus.COMPLETED, JobStatus.FAILED],
    stage_num: int = 0,
) -> bool:
    """Finish a processing task and commit if the caller still owns the job claim."""

    release_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
            MemoryChapterTask.stage_num == stage_num,
            MemoryChapterTask.task_status == JobStatus.PROCESSING,
            _owns_job_claim(memory_job_id, claim_token),
        )
        .values(task_status=task_status)
        .returning(MemoryChapterTask.chapter_id)
    )

    try:
        released_chapter_id = db.scalar(release_stmt)
        if released_chapter_id is None:
            db.rollback()
            return False
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def reset_failed_task(
    db: Session,
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
    stage_num: int = 0,
) -> bool:
    """Return a failed task to pending so a worker can claim it again."""
    reset_chapter_id = db.scalar(
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
            MemoryChapterTask.stage_num == stage_num,
            MemoryChapterTask.task_status == JobStatus.FAILED,
        )
        .values(task_status=JobStatus.PENDING)
        .returning(MemoryChapterTask.chapter_id)
    )
    if reset_chapter_id is None:
        db.rollback()
        return False
    db.commit()
    return True
