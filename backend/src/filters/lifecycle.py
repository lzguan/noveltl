"""Atomic lifecycle transitions for filter jobs."""

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.filters.models import Grouping, GroupingStatus, Workflow, WorkflowStatus


def _ids(values: Collection[UUID]) -> tuple[UUID, ...]:
    """Deduplicate resource IDs into a stable lock order."""
    return tuple(sorted(set(values)))


def _lock_workflows(db: Session, workflow_ids: tuple[UUID, ...]) -> dict[UUID, Workflow]:
    if not workflow_ids:
        return {}
    workflows = db.scalars(
        select(Workflow)
        .where(Workflow.workflow_id.in_(workflow_ids))
        .order_by(Workflow.workflow_id)
        .with_for_update()
    ).all()
    return {workflow.workflow_id: workflow for workflow in workflows}


def _lock_groupings(db: Session, grouping_ids: tuple[UUID, ...]) -> dict[UUID, Grouping]:
    if not grouping_ids:
        return {}
    groupings = db.scalars(
        select(Grouping)
        .where(Grouping.grouping_id.in_(grouping_ids))
        .order_by(Grouping.grouping_id)
        .with_for_update()
    ).all()
    return {grouping.grouping_id: grouping for grouping in groupings}


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
    be complete, or failed when ``allow_failed`` is true; neighbours must be at
    rest (complete or failed). On success, every member receives ``job_id`` and
    moves to pending in the caller's transaction.

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
            select(Grouping.grouping_id, Grouping.workflow_id).where(
                Grouping.grouping_id.in_(member_grouping_ids)
            )
        ).all()
    }
    if len(grouping_parents) != len(member_grouping_ids):
        return False

    locked_workflow_ids = _ids((*member_workflow_ids, *grouping_parents.values()))
    locked_workflows = _lock_workflows(db, locked_workflow_ids)
    if len(locked_workflows) != len(locked_workflow_ids):
        return False

    workflow_neighbour_grouping_ids = tuple(
        db.scalars(
            select(Grouping.grouping_id).where(Grouping.workflow_id.in_(member_workflow_ids))
        ).all()
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

    member_workflow_states = {WorkflowStatus.COMPLETE}
    member_grouping_states = {GroupingStatus.COMPLETE}
    if allow_failed:
        member_workflow_states.add(WorkflowStatus.FAILED)
        member_grouping_states.add(GroupingStatus.FAILED)

    if any(
        locked_workflows[workflow_id].workflow_status not in member_workflow_states
        for workflow_id in member_workflow_ids
    ):
        return False
    if any(
        locked_groupings[grouping_id].grouping_status not in member_grouping_states
        for grouping_id in member_grouping_ids
    ):
        return False

    at_rest_workflow_states = {WorkflowStatus.COMPLETE, WorkflowStatus.FAILED}
    at_rest_grouping_states = {GroupingStatus.COMPLETE, GroupingStatus.FAILED}
    neighbour_workflow_ids = set(locked_workflow_ids).difference(member_workflow_ids)
    neighbour_grouping_ids = set(locked_grouping_ids).difference(member_grouping_ids)
    if any(
        locked_workflows[workflow_id].workflow_status not in at_rest_workflow_states
        for workflow_id in neighbour_workflow_ids
    ):
        return False
    if any(
        locked_groupings[grouping_id].grouping_status not in at_rest_grouping_states
        for grouping_id in neighbour_grouping_ids
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


def claim_fjob(
    db: Session,
    job_id: UUID,
    workflow_ids: Collection[UUID] = (),
    grouping_ids: Collection[UUID] = (),
) -> bool:
    """Atomically claim every pending member owned by ``job_id``.

    Returns false without changing any resource unless the entire requested set
    exists, is pending, and carries the supplied job ID. The caller owns the
    surrounding transaction.
    """
    member_workflow_ids = _ids(workflow_ids)
    member_grouping_ids = _ids(grouping_ids)
    if not member_workflow_ids and not member_grouping_ids:
        raise ValueError("A filter job must contain at least one workflow or grouping.")

    locked_workflows = _lock_workflows(db, member_workflow_ids)
    locked_groupings = _lock_groupings(db, member_grouping_ids)
    if len(locked_workflows) != len(member_workflow_ids) or len(locked_groupings) != len(member_grouping_ids):
        return False
    if any(
        locked_workflows[workflow_id].workflow_status != WorkflowStatus.PENDING
        or locked_workflows[workflow_id].job_id != job_id
        for workflow_id in member_workflow_ids
    ):
        return False
    if any(
        locked_groupings[grouping_id].grouping_status != GroupingStatus.PENDING
        or locked_groupings[grouping_id].job_id != job_id
        for grouping_id in member_grouping_ids
    ):
        return False

    if member_workflow_ids:
        db.execute(
            update(Workflow)
            .where(
                Workflow.workflow_id.in_(member_workflow_ids),
                Workflow.workflow_status == WorkflowStatus.PENDING,
                Workflow.job_id == job_id,
            )
            .values(workflow_status=WorkflowStatus.PROCESSING, workflow_message=None)
        )
    if member_grouping_ids:
        db.execute(
            update(Grouping)
            .where(
                Grouping.grouping_id.in_(member_grouping_ids),
                Grouping.grouping_status == GroupingStatus.PENDING,
                Grouping.job_id == job_id,
            )
            .values(grouping_status=GroupingStatus.PROCESSING, grouping_message=None)
        )
    return True
