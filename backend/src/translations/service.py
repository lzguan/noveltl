"""User-facing job controls; database transitions commit before queue dispatch."""

import logging
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.memory.models import MemoryGroup
from src.novels.models import Novel
from src.novels.permissions import novel_mod_access_select
from src.translations.actions.actions import ActionTask
from src.translations.actions.registry import ACTION_CALLBACKS, last_step
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


def _restart_state(task: TranslationTask, stage: TranslationStage, batch: TranslationBatch) -> State:
    """Back up only when the saved step's required artifact/ID is missing."""
    state = task.status
    if stage.action == "combine_chapter":
        return state
    if stage.action == "prune_memories" and stage.stage_num == 0 and batch.initial_file_id is None:
        return State.READY
    if state in (State.PROCESSED, State.FINALIZING) and task.provider_output_id is None:
        state = State.PROCESSING
    if state == State.PROCESSING and task.provider_batch_id is None:
        state = State.PREPARED
    if state in (State.PREPARED, State.SUBMITTING) and task.input_file_id is None:
        state = State.READY
    return state


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
        query = select(TranslationBatch).where(TranslationBatch.job_id == job_id)
        if batch_id is not None:
            query = query.where(TranslationBatch.batch_id == batch_id)
        batches = db.scalars(
            query.order_by(TranslationBatch.batch_id).with_for_update().execution_options(populate_existing=True)
        ).all()
        if batch_id is not None and not batches:
            raise TranslationNotFoundError("Translation batch not found")
        for batch in batches:
            rows = db.execute(
                select(TranslationTask, TranslationStage)
                .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
                .where(TranslationTask.batch_id == batch.batch_id, TranslationStage.job_id == job_id)
                .order_by(TranslationStage.stage_num)
                .with_for_update(of=TranslationTask)
                .execution_options(populate_existing=True)
            ).all()
            unfinished = [(row._t[0], row._t[1]) for row in rows if row._t[0].status != State.COMPLETE]
            if not unfinished:
                continue
            now = db.scalar(select(func.clock_timestamp()))
            if operation == "cancel":
                for task, _ in unfinished:
                    task.claim_token = task.claim_expires_at = None
                    task.failed_at, task.error = now, "Cancelled by user"
                result.affected_batch_ids.append(batch.batch_id)
                continue
            if any(
                task.claim_token is not None and task.claim_expires_at is not None and task.claim_expires_at > now
                for task, _ in unfinished
            ):
                continue
            task, stage = unfinished[0]
            if operation != "retry" and any(item.failed_at is not None for item, _ in unfinished):
                continue
            action = TypeAdapter(ActionName).validate_python(stage.action)
            if operation == "start":
                if stage.stage_num != 0 or task.status != State.READY:
                    continue
                dispatches.append((task.task_id, ACTION_CALLBACKS[action].entrypoint))
            else:
                state = _restart_state(task, stage, batch) if operation == "retry" else task.status
                step = last_step(action, state)
                if step is None:
                    continue
                if operation == "retry":
                    for item, _ in unfinished:
                        item.failed_at = item.error = None
                        item.claim_token = item.claim_expires_at = None
                    if step.expect == State.READY:
                        # Rebuilding requests invalidates provider IDs for the old input.
                        task.provider_batch_id = task.provider_output_id = None
                        task.input_file_id = task.output_file_id = None
                task.status = step.expect
                task.claim_token = task.claim_expires_at = None
                dispatches.append((task.task_id, step.dispatch))
            result.affected_batch_ids.append(batch.batch_id)
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
