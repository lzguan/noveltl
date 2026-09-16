"""User-facing job controls; database transitions commit before queue dispatch."""

import logging
from functools import partial
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import DateTime, and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory.models import MemoryGroup
from src.novels.models import Novel
from src.novels.permissions import novel_mod_access_select
from src.translations.actions.actions import ActionTask
from src.translations.actions.registry import ACTION_CALLBACKS, last_step, last_step_sql
from src.translations.models import TranslationBatch, TranslationJob, TranslationStage, TranslationTask
from src.translations.schemas import (
    PruneMemoriesStageCreate,
    TranslateWithMemoriesStageCreate,
    TranslationBatchRead,
    TranslationControlResult,
    TranslationJobCreate,
    TranslationJobRead,
    TranslationStageRead,
    TranslationTaskRead,
)
from src.translations.tasks.jobs import create_job
from src.translations.types import ActionName
from src.translations.types import TranslationTaskStatus as State

logger = logging.getLogger(__name__)
type Control = Literal["start", "resume", "cancel", "retry"]


class TranslationNotFoundError(LookupError):
    pass


def _job(db: Session, user: User, job_id: UUID) -> TranslationJob:
    query = (
        select(TranslationJob)
        .join(Novel, Novel.novel_id == TranslationJob.novel_id)
        .where(TranslationJob.job_id == job_id)
    )
    job = db.scalar(novel_mod_access_select(query, user, edit_only=True))
    if job is None:
        raise TranslationNotFoundError("Translation job not found")
    return job


def create_translation_job(db: Session, user: User, request: TranslationJobCreate) -> UUID:
    if (
        db.scalar(
            novel_mod_access_select(
                select(Novel.novel_id).where(Novel.novel_id == request.novel_id), user, edit_only=True
            )
        )
        is None
    ):
        raise TranslationNotFoundError("Novel not found")
    if request.stages[0].action == "combine_chapter":
        raise ValueError("combine_chapter requires a preceding stage")
    group_ids = {
        stage.config.memory_group_id
        for stage in request.stages
        if isinstance(stage, (PruneMemoriesStageCreate, TranslateWithMemoriesStageCreate))
        and stage.config.memory_group_id is not None
    }
    if group_ids:
        found = set(
            db.scalars(
                select(MemoryGroup.memory_group_id).where(
                    MemoryGroup.memory_group_id.in_(group_ids),
                    MemoryGroup.novel_id == request.novel_id,
                )
            )
        )
        if found != group_ids:
            raise ValueError("Memory groups must belong to the job's novel")
    return create_job(db, request)


def read_translation_job(db: Session, user: User, job_id: UUID) -> TranslationJobRead:
    job = _job(db, user, job_id)
    stages = db.scalars(
        select(TranslationStage).where(TranslationStage.job_id == job_id).order_by(TranslationStage.stage_num)
    ).all()
    batches = db.scalars(
        select(TranslationBatch).where(TranslationBatch.job_id == job_id).order_by(TranslationBatch.batch_num)
    ).all()
    tasks = db.scalars(
        select(TranslationTask)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationTask.batch_id, TranslationStage.stage_num)
    ).all()
    return TranslationJobRead(
        job_id=job.job_id,
        novel_id=job.novel_id,
        config=job.config,
        stages=[TranslationStageRead.model_validate(stage) for stage in stages],
        batches=[TranslationBatchRead.model_validate(batch) for batch in batches],
        tasks=[TranslationTaskRead.model_validate(task) for task in tasks],
    )


def _restart_state_sql():
    """Walk back to the earliest missing artifact before resolving an action step."""
    state = TranslationTask.status
    state = case(
        (
            and_(state.in_((State.PROCESSED, State.FINALIZING)), TranslationTask.provider_output_id.is_(None)),
            str(State.PROCESSING),
        ),
        else_=state,
    )
    state = case(
        (and_(state == State.PROCESSING, TranslationTask.provider_batch_id.is_(None)), str(State.PREPARED)), else_=state
    )
    state = case(
        (
            and_(state.in_((State.PREPARED, State.SUBMITTING)), TranslationTask.input_file_id.is_(None)),
            str(State.READY),
        ),
        else_=state,
    )
    return case(
        (TranslationStage.action == "combine_chapter", TranslationTask.status),
        (
            and_(
                TranslationStage.action == "prune_memories",
                TranslationStage.stage_num == 0,
                TranslationBatch.initial_file_id.is_(None),
            ),
            str(State.READY),
        ),
        else_=state,
    )


def _control_statement(job_id: UUID, operation: Control, batch_id: UUID | None):
    """
    Heavenly sql good luck reading ts
    """
    task = TranslationTask
    scope = [TranslationStage.job_id == job_id, task.status != State.COMPLETE]
    if batch_id is not None:
        scope.append(task.batch_id == batch_id)
    if operation == "cancel":
        # Direct predicates are rechecked by PostgreSQL if a worker completes while
        # this UPDATE waits. Mark future tasks too, so handoff cannot undo cancel.
        return (
            update(task)
            .where(task.stage_id == TranslationStage.stage_id, *scope)
            .values(
                failed_at=func.clock_timestamp(), error="Cancelled by user", claim_token=None, claim_expires_at=None
            )
            .returning(task.task_id, task.batch_id, TranslationStage.action, task.status)
            .execution_options(synchronize_session=False)
        )

    live = and_(task.claim_token.is_not(None), task.claim_expires_at > func.clock_timestamp())
    state = _restart_state_sql() if operation == "retry" else task.status
    # Rank only unfinished tasks. Retry also clears failures on later tasks, but
    # only the first unfinished task in each batch is reset and dispatched.
    snapshot = (
        select(
            task.task_id,
            task.batch_id,
            task.status.label("old_status"),
            task.claim_token.label("old_token"),
            task.claim_expires_at.label("old_expiry"),
            task.failed_at.label("old_failure"),
            task.next_poll_at.label("old_next_poll"),
            TranslationStage.action,
            TranslationStage.stage_num,
            func.row_number().over(partition_by=task.batch_id, order_by=TranslationStage.stage_num).label("position"),
            func.bool_or(live).over(partition_by=task.batch_id).label("live_batch"),
            func.bool_or(task.failed_at.is_not(None)).over(partition_by=task.batch_id).label("failed_batch"),
            last_step_sql(TranslationStage.action, state).label("restart"),
        )
        .join(TranslationStage, TranslationStage.stage_id == task.stage_id)
        .join(TranslationBatch, TranslationBatch.batch_id == task.batch_id)
        .where(*scope)
        .cte("control_candidates")
    )
    current = snapshot.c.position == 1
    # Recheck against the UPDATE target: its row may have changed since the CTE
    # snapshot while PostgreSQL waited for a worker's write to commit.
    eligible = [
        task.task_id == snapshot.c.task_id,
        snapshot.c.live_batch.is_(False),
        task.status == snapshot.c.old_status,
        task.claim_token.is_not_distinct_from(snapshot.c.old_token),
        task.claim_expires_at.is_not_distinct_from(snapshot.c.old_expiry),
        task.failed_at.is_not_distinct_from(snapshot.c.old_failure),
        task.next_poll_at.is_not_distinct_from(snapshot.c.old_next_poll),
        or_(task.claim_token.is_(None), task.claim_expires_at <= func.clock_timestamp()),
    ]
    if operation != "retry":
        eligible.extend([snapshot.c.failed_batch.is_(False), current])
    if operation == "start":
        eligible.extend([snapshot.c.stage_num == 0, task.status == State.READY])
    eligible.append(or_(~current, snapshot.c.restart.is_not(None)))
    statement = (
        update(task)
        .where(*eligible)
        .values(
            status=case((current, snapshot.c.restart), else_=task.status),
            next_poll_at=case((and_(current, snapshot.c.restart != task.status), None), else_=task.next_poll_at),
            claim_token=None,
            claim_expires_at=None,
        )
    )
    if operation == "retry":
        rebuild = and_(current, snapshot.c.restart == State.READY)
        statement = statement.values(
            failed_at=None,
            error=None,
            provider_batch_id=case((rebuild, None), else_=task.provider_batch_id),
            provider_output_id=case((rebuild, None), else_=task.provider_output_id),
            input_file_id=case((rebuild, None), else_=task.input_file_id),
            output_file_id=case((rebuild, None), else_=task.output_file_id),
        )
    poll_in = task.next_poll_at - func.clock_timestamp(type_=DateTime(timezone=True))
    return statement.returning(
        task.task_id, task.batch_id, snapshot.c.action, task.status, snapshot.c.position, poll_in.label("poll_in")
    ).execution_options(synchronize_session=False)


def control_translation_job(
    db: Session,
    user: User,
    job_id: UUID,
    operation: Control,
    *,
    batch_id: UUID | None = None,
) -> TranslationControlResult:
    result = TranslationControlResult()
    dispatches: list[tuple[UUID, ActionTask]] = []
    try:
        _job(db, user, job_id)
        if (
            batch_id is not None
            and db.scalar(
                select(TranslationBatch.batch_id).where(
                    TranslationBatch.job_id == job_id,
                    TranslationBatch.batch_id == batch_id,
                )
            )
            is None
        ):
            raise TranslationNotFoundError("Translation batch not found")
        rows = db.execute(_control_statement(job_id, operation, batch_id)).all()
        result.affected_batch_ids = list(dict.fromkeys(row._t[1] for row in rows))
        if operation != "cancel":
            for row in rows:
                task_id, _, name, state, position, poll_in = row._t
                if position != 1:
                    continue
                action = TypeAdapter(ActionName).validate_python(name)
                if operation == "start":
                    dispatches.append((task_id, ACTION_CALLBACKS[action].entrypoint))
                else:
                    step = last_step(action, State(state))
                    if step is not None:
                        dispatches.append((task_id, partial(step.dispatch, delay=poll_in)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    for task_id, dispatch in dispatches:
        try:
            dispatch(task_id)
        except Exception:
            logger.exception("Translation dispatch failed for task %s", task_id)
            result.dispatch_failed_task_ids.append(task_id)
        else:
            result.dispatched_task_ids.append(task_id)
    return result
