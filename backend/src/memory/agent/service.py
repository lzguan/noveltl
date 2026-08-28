"""Permission-aware service operations for memory-agent jobs."""

from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory.agent import schemas
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.tasks.jobs import JobParams, make_job
from src.memory.agent.tasks.jobs import abort_job as abort_job_claim
from src.memory.exceptions import (
    MemoryAgentEnqueueFailedException,
    MemoryChapterTaskNotFoundException,
    MemoryChapterTaskStateException,
    MemoryGroupNotFoundException,
    MemoryJobNotFoundException,
    MemoryJobStateException,
)
from src.memory.models import MemoryChapterTask as MemoryChapterTaskModel
from src.memory.models import MemoryGroup
from src.memory.models import MemoryJob as MemoryJobModel
from src.memory.permissions import memory_group_mod_access_select
from src.memory.types import JobStatus
from src.novels.models import Chapter


def create_job(
    db: Session,
    user: User,
    memory_group_id: UUID,
    start_chapter_num: int | None,
    end_chapter_num: int | None,
    params: JobParams,
) -> schemas.MemoryJob:
    """Create a pending job for chapters in an editable memory group."""
    statement = select(MemoryGroup).where(MemoryGroup.memory_group_id == memory_group_id)
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryGroupNotFoundException(f"Memory group {memory_group_id} not found or not accessible.") from exc

    memory_job_id = make_job(db, memory_group_id, start_chapter_num, end_chapter_num, params)
    return query_job(db, user, memory_job_id)


def query_jobs(db: Session, user: User, memory_group_id: UUID) -> list[schemas.MemoryJob]:
    """Return jobs belonging to an accessible memory group, newest first."""
    group_statement = select(MemoryGroup).where(MemoryGroup.memory_group_id == memory_group_id)
    group_statement = memory_group_mod_access_select(group_statement, user)
    try:
        db.execute(group_statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryGroupNotFoundException(f"Memory group {memory_group_id} not found or not accessible.") from exc

    statement = (
        select(MemoryJobModel)
        .where(MemoryJobModel.memory_group_id == memory_group_id)
        .order_by(MemoryJobModel.created_at.desc(), MemoryJobModel.memory_job_id)
    )
    return [schemas.MemoryJob.model_validate(job) for job in db.scalars(statement).all()]


def query_job(db: Session, user: User, memory_job_id: UUID) -> schemas.MemoryJob:
    """Return one accessible memory-agent job without exposing its claim token."""
    statement = (
        select(MemoryJobModel)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(MemoryJobModel.memory_job_id == memory_job_id)
    )
    statement = memory_group_mod_access_select(statement, user)
    try:
        return schemas.MemoryJob.model_validate(db.execute(statement).scalar_one())
    except NoResultFound as exc:
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} not found or not accessible.") from exc


def query_tasks(
    db: Session,
    user: User,
    memory_job_id: UUID,
    skip: int = 0,
    limit: int = 100,
) -> schemas.MemoryChapterTaskPage:
    """Return a page of a job's chapter tasks in chapter order."""
    job_statement = (
        select(MemoryJobModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(MemoryJobModel.memory_job_id == memory_job_id)
    )
    job_statement = memory_group_mod_access_select(job_statement, user)
    try:
        db.execute(job_statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} not found or not accessible.") from exc

    rows = db.execute(
        select(
            MemoryChapterTaskModel.memory_job_id,
            MemoryChapterTaskModel.chapter_id,
            Chapter.chapter_num,
            MemoryChapterTaskModel.task_status,
            MemoryChapterTaskModel.attempt_count,
            MemoryChapterTaskModel.created_at,
            MemoryChapterTaskModel.updated_at,
        )
        .join(Chapter, Chapter.chapter_id == MemoryChapterTaskModel.chapter_id)
        .where(MemoryChapterTaskModel.memory_job_id == memory_job_id)
        .order_by(Chapter.chapter_num, Chapter.chapter_id)
        .offset(skip)
        .limit(limit)
    ).mappings()
    count = db.scalar(
        select(func.count())
        .select_from(MemoryChapterTaskModel)
        .where(MemoryChapterTaskModel.memory_job_id == memory_job_id)
    )
    return schemas.MemoryChapterTaskPage(
        count=count or 0,
        rows=[schemas.MemoryChapterTask.model_validate(row) for row in rows],
    )


def query_task(
    db: Session,
    user: User,
    memory_job_id: UUID,
    chapter_id: UUID,
) -> schemas.MemoryChapterTask:
    """Return one accessible chapter task."""
    statement = (
        select(
            MemoryChapterTaskModel.memory_job_id,
            MemoryChapterTaskModel.chapter_id,
            Chapter.chapter_num,
            MemoryChapterTaskModel.task_status,
            MemoryChapterTaskModel.attempt_count,
            MemoryChapterTaskModel.created_at,
            MemoryChapterTaskModel.updated_at,
        )
        .join(MemoryJobModel, MemoryJobModel.memory_job_id == MemoryChapterTaskModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .join(Chapter, Chapter.chapter_id == MemoryChapterTaskModel.chapter_id)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
        )
    )
    statement = memory_group_mod_access_select(statement, user)
    try:
        return schemas.MemoryChapterTask.model_validate(db.execute(statement).mappings().one())
    except NoResultFound as exc:
        raise MemoryChapterTaskNotFoundException(
            f"Memory task for job {memory_job_id} and chapter {chapter_id} not found or not accessible."
        ) from exc


def start_job(
    db: Session,
    user: User,
    dispatcher: MemoryAgentDispatcher,
    memory_job_id: UUID,
) -> schemas.MemoryJob:
    """Publish a job containing pending or abandoned processing work."""
    statement = (
        select(MemoryJobModel)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(MemoryJobModel.memory_job_id == memory_job_id)
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        job = db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} not found or not accessible.") from exc

    has_runnable_task = db.scalar(
        select(MemoryChapterTaskModel.chapter_id)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.task_status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
        )
        .limit(1)
    )
    if has_runnable_task is None:
        raise MemoryJobStateException(f"Memory job {memory_job_id} has no runnable tasks.")
    dispatcher.enqueue_job(memory_job_id)
    return schemas.MemoryJob.model_validate(job)


def start_task(
    db: Session,
    user: User,
    dispatcher: MemoryAgentDispatcher,
    memory_job_id: UUID,
    chapter_id: UUID,
) -> schemas.MemoryChapterTask:
    """Publish one pending chapter task after checking edit access."""
    statement = (
        select(MemoryChapterTaskModel, Chapter.chapter_num)
        .join(MemoryJobModel, MemoryJobModel.memory_job_id == MemoryChapterTaskModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .join(Chapter, Chapter.chapter_id == MemoryChapterTaskModel.chapter_id)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
        )
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        task, chapter_num = db.execute(statement).one()._t
    except NoResultFound as exc:
        raise MemoryChapterTaskNotFoundException(
            f"Memory task for job {memory_job_id} and chapter {chapter_id} not found or not accessible."
        ) from exc

    if task.task_status != JobStatus.PENDING:
        raise MemoryChapterTaskStateException(f"Memory task for chapter {chapter_id} is not pending.")
    dispatcher.enqueue_task(memory_job_id, chapter_id)
    return schemas.MemoryChapterTask(
        memory_job_id=task.memory_job_id,
        chapter_id=task.chapter_id,
        chapter_num=chapter_num,
        task_status=task.task_status,
        attempt_count=task.attempt_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def retry_task(
    db: Session,
    user: User,
    dispatcher: MemoryAgentDispatcher,
    memory_job_id: UUID,
    chapter_id: UUID,
) -> schemas.MemoryChapterTask:
    """Reset one failed task to pending and publish it again."""
    statement = (
        select(MemoryChapterTaskModel.memory_job_id)
        .join(MemoryJobModel, MemoryJobModel.memory_job_id == MemoryChapterTaskModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
        )
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryChapterTaskNotFoundException(
            f"Memory task for job {memory_job_id} and chapter {chapter_id} not found or not accessible."
        ) from exc

    task = db.scalar(
        update(MemoryChapterTaskModel)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
            MemoryChapterTaskModel.task_status == JobStatus.FAILED,
        )
        .values(task_status=JobStatus.PENDING)
        .returning(MemoryChapterTaskModel)
    )
    if task is None:
        db.rollback()
        raise MemoryChapterTaskStateException(f"Memory task for chapter {chapter_id} is not failed.")
    db.commit()

    try:
        dispatcher.enqueue_task(memory_job_id, chapter_id)
    except MemoryAgentEnqueueFailedException:
        db.execute(
            update(MemoryChapterTaskModel)
            .where(
                MemoryChapterTaskModel.memory_job_id == memory_job_id,
                MemoryChapterTaskModel.chapter_id == chapter_id,
                MemoryChapterTaskModel.task_status == JobStatus.PENDING,
            )
            .values(task_status=JobStatus.FAILED)
        )
        db.commit()
        raise
    return query_task(db, user, memory_job_id, chapter_id)


def abort_job(db: Session, user: User, memory_job_id: UUID) -> schemas.MemoryJob:
    """Fail active tasks and clear the claim on an accessible memory job."""
    statement = (
        select(MemoryJobModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(MemoryJobModel.memory_job_id == memory_job_id)
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} not found or not accessible.") from exc

    if not abort_job_claim(db, memory_job_id):
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} no longer exists.")
    return query_job(db, user, memory_job_id)


def delete_task(db: Session, user: User, memory_job_id: UUID, chapter_id: UUID) -> None:
    """Delete a non-processing chapter task."""
    statement = (
        select(MemoryChapterTaskModel)
        .join(MemoryJobModel, MemoryJobModel.memory_job_id == MemoryChapterTaskModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
        )
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        task = db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryChapterTaskNotFoundException(
            f"Memory task for job {memory_job_id} and chapter {chapter_id} not found or not accessible."
        ) from exc

    if task.task_status == JobStatus.PROCESSING:
        raise MemoryChapterTaskStateException(f"Memory task for chapter {chapter_id} is processing.")
    deleted_chapter_id = db.scalar(
        delete(MemoryChapterTaskModel)
        .where(
            MemoryChapterTaskModel.memory_job_id == memory_job_id,
            MemoryChapterTaskModel.chapter_id == chapter_id,
            MemoryChapterTaskModel.task_status != JobStatus.PROCESSING,
        )
        .returning(MemoryChapterTaskModel.chapter_id)
    )
    if deleted_chapter_id is None:
        db.rollback()
        raise MemoryChapterTaskStateException(f"Memory task for chapter {chapter_id} changed state.")
    db.commit()


def delete_job(db: Session, user: User, memory_job_id: UUID) -> None:
    """Delete an unclaimed or expired job and cascade its chapter tasks."""
    statement = (
        select(MemoryJobModel.memory_job_id)
        .join(MemoryGroup, MemoryGroup.memory_group_id == MemoryJobModel.memory_group_id)
        .where(MemoryJobModel.memory_job_id == memory_job_id)
    )
    statement = memory_group_mod_access_select(statement, user, edit_only=True)
    try:
        db.execute(statement).scalar_one()
    except NoResultFound as exc:
        raise MemoryJobNotFoundException(f"Memory job {memory_job_id} not found or not accessible.") from exc

    deleted_job_id = db.scalar(
        delete(MemoryJobModel)
        .where(
            MemoryJobModel.memory_job_id == memory_job_id,
            or_(
                MemoryJobModel.claim_token.is_(None),
                MemoryJobModel.claim_expires_at < func.now(),
            ),
        )
        .returning(MemoryJobModel.memory_job_id)
    )
    if deleted_job_id is None:
        db.rollback()
        raise MemoryJobStateException(f"Memory job {memory_job_id} is currently claimed.")
    db.commit()
