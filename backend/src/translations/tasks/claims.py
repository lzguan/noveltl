"""Claim transitions. Callers own transactions; no helper commits."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from src.translations.models import TranslationBatch, TranslationTask
from src.translations.types import TranslationTaskStatus


class TranslationClaimLostError(RuntimeError):
    pass


def claim_task(
    db: Session,
    task_id: UUID,
    token: UUID,
    *,
    expect: TranslationTaskStatus,
    during: TranslationTaskStatus,
    duration: timedelta,
) -> bool:
    if duration <= timedelta(0):
        raise ValueError("Claim duration must be positive")
    return (
        db.scalar(
            update(TranslationTask)
            .where(
                TranslationTask.task_id == task_id,
                TranslationTask.failed_at.is_(None),
                or_(TranslationTask.next_poll_at.is_(None), TranslationTask.next_poll_at <= func.clock_timestamp()),
                or_(
                    and_(TranslationTask.status == expect, TranslationTask.claim_token.is_(None)),
                    and_(
                        TranslationTask.status == during,
                        TranslationTask.claim_expires_at <= func.clock_timestamp(),
                    ),
                ),
            )
            .values(status=during, claim_token=token, claim_expires_at=func.clock_timestamp() + duration)
            .returning(TranslationTask.task_id)
        )
        is not None
    )


def _owned(task_id: UUID, token: UUID, during: TranslationTaskStatus):
    return and_(
        TranslationTask.task_id == task_id,
        TranslationTask.claim_token == token,
        TranslationTask.claim_expires_at > func.clock_timestamp(),
        TranslationTask.status == during,
        TranslationTask.failed_at.is_(None),
    )


def renew_claim(db: Session, task_id: UUID, token: UUID, *, during: TranslationTaskStatus, duration: timedelta) -> bool:
    if duration <= timedelta(0):
        raise ValueError("Claim duration must be positive")
    return (
        db.scalar(
            update(TranslationTask)
            .where(_owned(task_id, token, during))
            .values(claim_expires_at=func.clock_timestamp() + duration)
            .returning(TranslationTask.task_id)
        )
        is not None
    )


def finish_claim(
    db: Session,
    task_id: UUID,
    token: UUID,
    *,
    during: TranslationTaskStatus,
    finish: TranslationTaskStatus,
    poll_interval: timedelta | None = None,
) -> None:
    """Fence callback writes before flushing them; stale workers must roll back.

    Use wall-clock time because the callback transaction may have started long
    before its lease expired. The guarded update locks the row through commit.
    """
    if poll_interval is not None and poll_interval <= timedelta(0):
        raise ValueError("Poll interval must be positive")
    with db.no_autoflush:
        owned = db.scalar(
            update(TranslationTask)
            .where(_owned(task_id, token, during))
            .values(
                status=finish,
                claim_token=None,
                claim_expires_at=None,
                next_poll_at=func.clock_timestamp() + poll_interval if poll_interval is not None else None,
            )
            .returning(TranslationTask.task_id)
            .execution_options(synchronize_session=False)
        )
    if owned is None:
        raise TranslationClaimLostError(f"Lost translation task claim: {task_id}")
    db.flush()


def publish_initial_file(db: Session, task_id: UUID, token: UUID, file_id: UUID) -> None:
    """Write the batch artifact before completion updates the task, in its transaction.

    The later finish_claim check still fences the entire transaction if ownership
    changes concurrently. Never leave this batch mutation pending in the ORM.
    """
    owner = (
        select(TranslationTask.batch_id)
        .where(_owned(task_id, token, TranslationTaskStatus.PREPARING))
        .scalar_subquery()
    )
    with db.no_autoflush:
        published = db.scalar(
            update(TranslationBatch)
            .where(
                TranslationBatch.batch_id == owner,
                TranslationBatch.initial_file_id.is_(None),
            )
            .values(initial_file_id=file_id)
            .returning(TranslationBatch.batch_id)
            .execution_options(synchronize_session=False)
        )
    if published is None:
        raise TranslationClaimLostError(f"Lost initial artifact publication claim: {task_id}")


def fail_claim(db: Session, task_id: UUID, token: UUID, *, during: TranslationTaskStatus, error: str) -> bool:
    """Record failure after callback writes have been rolled back."""
    return (
        db.scalar(
            update(TranslationTask)
            .where(_owned(task_id, token, during))
            .values(failed_at=func.clock_timestamp(), error=error, claim_token=None, claim_expires_at=None)
            .returning(TranslationTask.task_id)
        )
        is not None
    )
