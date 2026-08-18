"""Atomic lifecycle transitions for filter jobs."""

from collections.abc import Collection
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.filters.models import Grouping, GroupingStatus, Workflow, WorkflowStatus


class _WorkflowState(NamedTuple):
    status: WorkflowStatus
    job_id: UUID | None


class _GroupingState(NamedTuple):
    workflow_id: UUID
    status: GroupingStatus
    job_id: UUID | None


def _ids(values: Collection[UUID]) -> tuple[UUID, ...]:
    """Deduplicate resource IDs into a stable lock order."""
    return tuple(sorted(set(values)))


def _lock_workflows(db: Session, workflow_ids: tuple[UUID, ...]) -> dict[UUID, _WorkflowState]:
    if not workflow_ids:
        return {}
    workflows = db.execute(
        select(
            Workflow.workflow_id,
            Workflow.workflow_status,
            Workflow.job_id,
        )
        .where(Workflow.workflow_id.in_(workflow_ids))
        .order_by(Workflow.workflow_id)
        .with_for_update()
    ).all()
    return {workflow_id: _WorkflowState(status=status, job_id=job_id) for workflow_id, status, job_id in workflows}


def _lock_groupings(db: Session, grouping_ids: tuple[UUID, ...]) -> dict[UUID, _GroupingState]:
    if not grouping_ids:
        return {}
    groupings = db.execute(
        select(
            Grouping.grouping_id,
            Grouping.workflow_id,
            Grouping.grouping_status,
            Grouping.job_id,
        )
        .where(Grouping.grouping_id.in_(grouping_ids))
        .order_by(Grouping.grouping_id)
        .with_for_update()
    ).all()
    return {
        grouping_id: _GroupingState(workflow_id=workflow_id, status=status, job_id=job_id)
        for grouping_id, workflow_id, status, job_id in groupings
    }


def _lock_fjob(
    db: Session,
    job_id: UUID,
) -> (
    tuple[
        tuple[UUID, ...],
        tuple[UUID, ...],
        dict[UUID, _WorkflowState],
        dict[UUID, _GroupingState],
    ]
    | None
):
    workflow_ids = tuple(
        db.scalars(select(Workflow.workflow_id).where(Workflow.job_id == job_id).order_by(Workflow.workflow_id)).all()
    )
    grouping_ids = tuple(
        db.scalars(select(Grouping.grouping_id).where(Grouping.job_id == job_id).order_by(Grouping.grouping_id)).all()
    )
    if not workflow_ids and not grouping_ids:
        return None

    workflows = _lock_workflows(db, workflow_ids)
    groupings = _lock_groupings(db, grouping_ids)
    if len(workflows) != len(workflow_ids) or len(groupings) != len(grouping_ids):
        return None
    return workflow_ids, grouping_ids, workflows, groupings


def queue_fjob(
    db: Session,
    job_id: UUID,
    workflow_ids: Collection[UUID] = (),
    grouping_ids: Collection[UUID] = (),
    *,
    allow_failed: bool = True,
) -> bool:
    """Reserve existing filter resources for a job.

    Explicitly supplied workflows and groupings are job members. A workflow's
    groupings and a grouping's workflow are immediate neighbours. Members must
    be new or complete, or failed when ``allow_failed`` is true; neighbours
    must be at rest (complete or failed). On success, every member receives
    ``job_id`` and moves to pending in the caller's transaction.

    Returns false without changing any resource if a member or neighbour is
    missing or has an incompatible status.
    """
    member_workflow_ids = _ids(workflow_ids)
    member_grouping_ids = _ids(grouping_ids)
    if not member_workflow_ids and not member_grouping_ids:
        raise ValueError("A filter job must contain at least one workflow or grouping.")

    # Resolve parent workflows before taking locks so every operation acquires
    # workflow locks before grouping locks. Relationships are checked again
    # when the grouping rows themselves are locked.
    grouping_parents = {
        grouping_id: workflow_id
        for grouping_id, workflow_id in db.execute(
            select(Grouping.grouping_id, Grouping.workflow_id).where(Grouping.grouping_id.in_(member_grouping_ids))
        ).all()
    }
    if len(grouping_parents) != len(member_grouping_ids):
        return False

    locked_workflow_ids = _ids((*member_workflow_ids, *grouping_parents.values()))
    locked_workflows = _lock_workflows(db, locked_workflow_ids)
    if len(locked_workflows) != len(locked_workflow_ids):
        return False

    workflow_neighbour_grouping_ids = tuple(
        db.scalars(select(Grouping.grouping_id).where(Grouping.workflow_id.in_(member_workflow_ids))).all()
    )
    locked_grouping_ids = _ids((*member_grouping_ids, *workflow_neighbour_grouping_ids))
    locked_groupings = _lock_groupings(db, locked_grouping_ids)
    if len(locked_groupings) != len(locked_grouping_ids):
        return False
    if any(
        locked_groupings[grouping_id].workflow_id != workflow_id
        for grouping_id, workflow_id in grouping_parents.items()
    ):
        return False

    member_workflow_states = {WorkflowStatus.NEW, WorkflowStatus.COMPLETE}
    member_grouping_states = {GroupingStatus.NEW, GroupingStatus.COMPLETE}
    if allow_failed:
        member_workflow_states.add(WorkflowStatus.FAILED)
        member_grouping_states.add(GroupingStatus.FAILED)

    if any(locked_workflows[workflow_id].status not in member_workflow_states for workflow_id in member_workflow_ids):
        return False
    if any(locked_groupings[grouping_id].status not in member_grouping_states for grouping_id in member_grouping_ids):
        return False

    at_rest_workflow_states = {WorkflowStatus.COMPLETE, WorkflowStatus.FAILED}
    at_rest_grouping_states = {GroupingStatus.COMPLETE, GroupingStatus.FAILED}
    neighbour_workflow_ids = set(locked_workflow_ids).difference(member_workflow_ids)
    neighbour_grouping_ids = set(locked_grouping_ids).difference(member_grouping_ids)
    if any(
        locked_workflows[workflow_id].status not in at_rest_workflow_states for workflow_id in neighbour_workflow_ids
    ):
        return False
    if any(
        locked_groupings[grouping_id].status not in at_rest_grouping_states for grouping_id in neighbour_grouping_ids
    ):
        return False

    if member_workflow_ids:
        db.execute(
            update(Workflow)
            .where(Workflow.workflow_id.in_(member_workflow_ids))
            .values(job_id=job_id, workflow_status=WorkflowStatus.PENDING, workflow_message=None)
        )
    if member_grouping_ids:
        db.execute(
            update(Grouping)
            .where(Grouping.grouping_id.in_(member_grouping_ids))
            .values(job_id=job_id, grouping_status=GroupingStatus.PENDING, grouping_message=None)
        )
    return True


def _transition_fjob(
    db: Session,
    job_id: UUID,
    workflow_from: WorkflowStatus,
    workflow_to: WorkflowStatus,
    grouping_from: GroupingStatus,
    grouping_to: GroupingStatus,
    message: str | None,
) -> bool:
    fjob = _lock_fjob(db, job_id)
    if fjob is None:
        return False
    workflow_ids, grouping_ids, workflows, groupings = fjob
    if any(state.status != workflow_from or state.job_id != job_id for state in workflows.values()):
        return False
    if any(state.status != grouping_from or state.job_id != job_id for state in groupings.values()):
        return False

    if workflow_ids:
        db.execute(
            update(Workflow)
            .where(
                Workflow.workflow_id.in_(workflow_ids),
                Workflow.workflow_status == workflow_from,
                Workflow.job_id == job_id,
            )
            .values(workflow_status=workflow_to, workflow_message=message)
        )
    if grouping_ids:
        db.execute(
            update(Grouping)
            .where(
                Grouping.grouping_id.in_(grouping_ids),
                Grouping.grouping_status == grouping_from,
                Grouping.job_id == job_id,
            )
            .values(grouping_status=grouping_to, grouping_message=message)
        )
    return True


def claim_fjob(db: Session, job_id: UUID) -> bool:
    """Atomically move every pending member owned by ``job_id`` to processing."""
    return _transition_fjob(
        db,
        job_id,
        WorkflowStatus.PENDING,
        WorkflowStatus.PROCESSING,
        GroupingStatus.PENDING,
        GroupingStatus.PROCESSING,
        None,
    )


def clear_fjob(
    db: Session,
    job_id: UUID,
    new_stat: WorkflowStatus,
    message: str | None,
) -> bool:
    """Move an entire processing filter job to one terminal state."""
    if new_stat not in (WorkflowStatus.COMPLETE, WorkflowStatus.FAILED):
        raise ValueError("A filter job may only be cleared to complete or failed.")
    return _transition_fjob(
        db,
        job_id,
        WorkflowStatus.PROCESSING,
        new_stat,
        GroupingStatus.PROCESSING,
        GroupingStatus(new_stat.value),
        message,
    )


def abort_fjob(db: Session, job_id: UUID, message: str | None) -> bool:
    """Fail an entire pending filter job before it is claimed."""
    return _transition_fjob(
        db,
        job_id,
        WorkflowStatus.PENDING,
        WorkflowStatus.FAILED,
        GroupingStatus.PENDING,
        GroupingStatus.FAILED,
        message,
    )
