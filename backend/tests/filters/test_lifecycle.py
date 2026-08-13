from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.filters.data_types import Schema
from src.filters.lifecycle import abort_fjob, claim_fjob, clear_fjob, queue_fjob
from src.filters.models import FunctionDefinition, Grouping, GroupingStatus, Workflow, WorkflowStatus


def _workflow(db: Session, status: WorkflowStatus = WorkflowStatus.COMPLETE) -> Workflow:
    workflow = Workflow(schema=Schema().model_dump(mode="json"), workflow_status=status)
    db.add(workflow)
    db.flush()
    return workflow


def _grouping(
    db: Session,
    workflow: Workflow,
    name: str,
    status: GroupingStatus = GroupingStatus.COMPLETE,
) -> Grouping:
    function = FunctionDefinition(
        namespace="lifecycle-tests",
        function_name=name,
        function_definition={"name": "literalString", "value": name, "mutable": False},
    )
    db.add(function)
    db.flush()
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function.function_definition_id,
        grouping_status=status,
    )
    db.add(grouping)
    db.flush()
    return grouping


def test_queue_workflow_checks_grouping_neighbours_without_transitioning_them(test_db: Session) -> None:
    workflow = _workflow(test_db)
    grouping = _grouping(test_db, workflow, "word")
    test_db.commit()
    job_id = uuid4()

    assert queue_fjob(test_db, job_id, workflow_ids=[workflow.workflow_id])
    test_db.flush()

    assert workflow.workflow_status == WorkflowStatus.PENDING
    assert workflow.job_id == job_id
    assert grouping.grouping_status == GroupingStatus.COMPLETE
    assert grouping.job_id is None


def test_new_is_the_default_and_only_queueable_as_a_member(test_db: Session) -> None:
    workflow = Workflow(schema=Schema().model_dump(mode="json"))
    test_db.add(workflow)
    test_db.flush()
    new_neighbour = _grouping(test_db, workflow, "new-neighbour", GroupingStatus.NEW)
    test_db.commit()

    assert workflow.workflow_status == WorkflowStatus.NEW
    assert not queue_fjob(test_db, uuid4(), workflow_ids=[workflow.workflow_id])

    job_id = uuid4()
    assert queue_fjob(
        test_db,
        job_id,
        workflow_ids=[workflow.workflow_id],
        grouping_ids=[new_neighbour.grouping_id],
    )


def test_queue_rejects_non_resting_neighbour_without_mutation(test_db: Session) -> None:
    workflow = _workflow(test_db)
    grouping = _grouping(test_db, workflow, "word", GroupingStatus.PROCESSING)
    test_db.commit()

    assert not queue_fjob(test_db, uuid4(), workflow_ids=[workflow.workflow_id])

    assert workflow.workflow_status == WorkflowStatus.COMPLETE
    assert workflow.job_id is None
    assert grouping.grouping_status == GroupingStatus.PROCESSING


def test_queue_grouping_checks_parent_workflow_and_honours_allow_failed(test_db: Session) -> None:
    workflow = _workflow(test_db)
    grouping = _grouping(test_db, workflow, "word", GroupingStatus.FAILED)
    test_db.commit()
    job_id = uuid4()

    assert not queue_fjob(test_db, job_id, grouping_ids=[grouping.grouping_id], allow_failed=False)
    assert grouping.grouping_status == GroupingStatus.FAILED
    assert grouping.job_id is None

    assert queue_fjob(test_db, job_id, grouping_ids=[grouping.grouping_id], allow_failed=True)
    test_db.flush()
    assert grouping.grouping_status == GroupingStatus.PENDING
    assert grouping.job_id == job_id
    assert workflow.workflow_status == WorkflowStatus.COMPLETE


def test_claim_requires_every_member_to_be_pending_and_owned_by_job(test_db: Session) -> None:
    first = _workflow(test_db)
    second = _workflow(test_db)
    test_db.commit()
    job_id = uuid4()

    assert queue_fjob(test_db, job_id, workflow_ids=[first.workflow_id, second.workflow_id])
    test_db.flush()
    second.workflow_status = WorkflowStatus.COMPLETE
    test_db.flush()

    assert not claim_fjob(test_db, job_id)
    assert first.workflow_status == WorkflowStatus.PENDING
    assert second.workflow_status == WorkflowStatus.COMPLETE


def test_claim_transitions_workflows_and_groupings_together(test_db: Session) -> None:
    workflow = _workflow(test_db)
    grouping = _grouping(test_db, workflow, "word")
    test_db.commit()
    job_id = uuid4()

    assert queue_fjob(
        test_db,
        job_id,
        workflow_ids=[workflow.workflow_id],
        grouping_ids=[grouping.grouping_id],
    )
    assert claim_fjob(test_db, job_id)
    test_db.flush()

    assert workflow.workflow_status == WorkflowStatus.PROCESSING
    assert workflow.job_id == job_id
    assert grouping.grouping_status == GroupingStatus.PROCESSING
    assert grouping.job_id == job_id


def test_clear_transitions_the_entire_processing_job_uniformly(test_db: Session) -> None:
    workflow = _workflow(test_db)
    grouping = _grouping(test_db, workflow, "clear")
    test_db.commit()
    job_id = uuid4()
    assert queue_fjob(
        test_db,
        job_id,
        workflow_ids=[workflow.workflow_id],
        grouping_ids=[grouping.grouping_id],
    )
    assert claim_fjob(test_db, job_id)

    assert clear_fjob(test_db, job_id, WorkflowStatus.FAILED, "execution failed")
    test_db.flush()

    assert workflow.workflow_status == WorkflowStatus.FAILED
    assert workflow.workflow_message == "execution failed"
    assert workflow.job_id == job_id
    assert grouping.grouping_status == GroupingStatus.FAILED
    assert grouping.grouping_message == "execution failed"
    assert grouping.job_id == job_id
    assert not clear_fjob(test_db, job_id, WorkflowStatus.COMPLETE, None)


def test_abort_transitions_the_entire_pending_job_to_failed(test_db: Session) -> None:
    first = _workflow(test_db)
    second = _workflow(test_db)
    test_db.commit()
    job_id = uuid4()
    assert queue_fjob(test_db, job_id, workflow_ids=[first.workflow_id, second.workflow_id])

    assert abort_fjob(test_db, job_id, "publication failed")
    test_db.flush()

    assert first.workflow_status == WorkflowStatus.FAILED
    assert second.workflow_status == WorkflowStatus.FAILED
    assert first.workflow_message == second.workflow_message == "publication failed"
    assert not abort_fjob(test_db, job_id, "duplicate")


def test_lifecycle_helpers_handle_empty_jobs_and_invalid_terminal_state(test_db: Session) -> None:
    with pytest.raises(ValueError, match="at least one"):
        queue_fjob(test_db, uuid4())
    assert not claim_fjob(test_db, uuid4())
    assert not clear_fjob(test_db, uuid4(), WorkflowStatus.COMPLETE, None)
    assert not abort_fjob(test_db, uuid4(), "failure")
    with pytest.raises(ValueError, match="complete or failed"):
        clear_fjob(test_db, uuid4(), WorkflowStatus.PENDING, None)
