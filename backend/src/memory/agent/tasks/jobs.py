import uuid
from datetime import timedelta
from typing import Literal

from sqlalchemy import func, insert, literal, or_, select, update
from sqlalchemy.orm import Session

from src.memory.agent.agent import ModelName
from src.memory.models import MemoryChapterTask, MemoryGroup, MemoryJob
from src.memory.types import JobStatus, PluginName
from src.novels.models import Chapter
from src.schemas import Model


class JobParams(Model):
    model_name: ModelName
    plugins: list[PluginName]


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
    """Claim a job that has pending work and return its persisted configuration."""
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
    claim_stmt = (
        update(MemoryJob)
        .where(
            MemoryJob.memory_job_id == memory_job_id,
            has_pending_task,
            or_(
                MemoryJob.claim_token.is_(None),
                MemoryJob.claim_expires_at < func.now(),
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
    """Clear a job claim regardless of which worker currently owns it."""
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
        select(literal(memory_job_id), Chapter.chapter_id)
        .select_from(Chapter)
        .join(MemoryGroup, MemoryGroup.novel_id == Chapter.novel_id)
        .where(MemoryGroup.memory_group_id == memory_group_id)
    )
    if start_chapter_num is not None:
        chapter_query = chapter_query.where(Chapter.chapter_num >= start_chapter_num)
    if end_chapter_num is not None:
        chapter_query = chapter_query.where(Chapter.chapter_num < end_chapter_num)

    task_stmt = insert(MemoryChapterTask).from_select(
        [MemoryChapterTask.memory_job_id, MemoryChapterTask.chapter_id],
        chapter_query,
    )

    try:
        db.execute(job_stmt)
        db.execute(task_stmt)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return memory_job_id


def claim_next_task(
    db: Session,
    memory_job_id: uuid.UUID,
    claim_token: uuid.UUID,
) -> MemoryChapterTask | None:
    """
    Mark and return the next pending task while the caller owns the job claim.

    Args:
        db: The database session.
        memory_job_id: The ID of the job.
        claim_token: The token proving ownership of the job claim.
    Returns:
        The claimed task, or None if there is no pending task or the job claim
        is not currently owned by the caller.
    """
    next_chapter_id = (
        select(MemoryChapterTask.chapter_id)
        .join(Chapter, Chapter.chapter_id == MemoryChapterTask.chapter_id)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.task_status == JobStatus.PENDING,
            _owns_job_claim(memory_job_id, claim_token),
        )
        .order_by(Chapter.chapter_num, Chapter.chapter_id)
        .limit(1)
        .scalar_subquery()
    )
    claim_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == next_chapter_id,
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
) -> MemoryChapterTask | None:
    """Mark a specified pending task as processing while the caller owns the job claim."""
    claim_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
            MemoryChapterTask.task_status == JobStatus.PENDING,
            _owns_job_claim(memory_job_id, claim_token),
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
) -> bool:
    """Finish a processing task and commit if the caller still owns the job claim."""

    release_stmt = (
        update(MemoryChapterTask)
        .where(
            MemoryChapterTask.memory_job_id == memory_job_id,
            MemoryChapterTask.chapter_id == chapter_id,
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
