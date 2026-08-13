import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import DataObj, FloatData, Schema, StringData, StringField
from src.filters.lifecycle import queue_fjob
from src.filters.models import FunctionDefinition, Grouping, GroupingStatus, Instance, Workflow, WorkflowStatus
from src.filters.runners.python.annotation_runner import (
    NewFloatFieldRequest,
    NewStringFieldRequest,
    PythonAnnotationInput,
    PythonAnnotationRunner,
)
from src.schemas import Model

JOB_ID = uuid.UUID("80b312df-5464-4458-a09e-9b47c8983307")
STALE_JOB_ID = uuid.UUID("d0c03856-ff58-4b25-aed3-b18dd6a74b4d")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _workflow(db: Session, name: str = "Annotation workflow") -> Workflow:
    workflow = Workflow(
        workflow_name=name,
        schema=_dump(Schema(fields={"word": StringField()})),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    db.add(workflow)
    db.flush()
    return workflow


def _instance(db: Session, workflow: Workflow, word: str = "alpha") -> Instance:
    instance = Instance(
        workflow_id=workflow.workflow_id,
        value=_dump(DataObj(fields={"word": StringData(value=word)})),
    )
    db.add(instance)
    db.flush()
    return instance


def _input(workflow: Workflow, *, field_name: str = "note") -> PythonAnnotationInput:
    return PythonAnnotationInput(
        runner_name="annotation",
        runtime_name="python",
        workflow_id=workflow.workflow_id,
        new_fields={field_name: NewStringFieldRequest(type="string", default_value="review")},
    )


def test_annotation_runner_adds_mutable_fields_to_schema_and_instances(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    workflow = _workflow(test_db)
    instances = [_instance(test_db, workflow, "alpha"), _instance(test_db, workflow, "beta")]
    assert queue_fjob(test_db, JOB_ID, workflow_ids=(workflow.workflow_id,))
    test_db.commit()

    PythonAnnotationRunner(testing_session_local).execute(
        JOB_ID,
        PythonAnnotationInput(
            runner_name="annotation",
            runtime_name="python",
            workflow_id=workflow.workflow_id,
            new_fields={
                "note": NewStringFieldRequest(type="string", default_value="review"),
                "score": NewFloatFieldRequest(type="float", default_value=0.75),
            },
        ),
    )

    test_db.expire_all()
    stored_workflow = test_db.get(Workflow, workflow.workflow_id)
    assert stored_workflow is not None
    assert stored_workflow.workflow_status == WorkflowStatus.COMPLETE
    schema = Schema.model_validate(stored_workflow.schema)
    assert schema.fields["note"] == StringField(mutable=True)
    assert schema.fields["score"].mutable

    stored_values = test_db.scalars(
        select(Instance.value)
        .where(Instance.instance_id.in_([instance.instance_id for instance in instances]))
        .order_by(Instance.instance_id)
    )
    for raw_value in stored_values:
        value = DataObj.model_validate(raw_value)
        assert value.fields["note"] == StringData(value="review")
        assert value.fields["score"] == FloatData(value=0.75)


def test_annotation_runner_fails_duplicate_field_without_changing_instances(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    workflow = _workflow(test_db)
    instance = _instance(test_db, workflow)
    original_value = instance.value
    assert queue_fjob(test_db, JOB_ID, workflow_ids=(workflow.workflow_id,))
    test_db.commit()

    with pytest.raises(ValueError, match="already exists"):
        PythonAnnotationRunner(testing_session_local).execute(JOB_ID, _input(workflow, field_name="word"))

    test_db.expire_all()
    stored_workflow = test_db.get(Workflow, workflow.workflow_id)
    stored_instance = test_db.get(Instance, instance.instance_id)
    assert stored_workflow is not None and stored_workflow.workflow_status == WorkflowStatus.FAILED
    assert stored_instance is not None and stored_instance.value == original_value


def test_annotation_runner_rejects_input_workflow_outside_claimed_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    claimed_workflow = _workflow(test_db, "Claimed")
    input_workflow = _workflow(test_db, "Input")
    input_instance = _instance(test_db, input_workflow)
    original_value = input_instance.value
    assert queue_fjob(test_db, JOB_ID, workflow_ids=(claimed_workflow.workflow_id,))
    test_db.commit()

    with pytest.raises(ValueError, match="exactly its input workflow"):
        PythonAnnotationRunner(testing_session_local).execute(JOB_ID, _input(input_workflow))

    test_db.expire_all()
    claimed = test_db.get(Workflow, claimed_workflow.workflow_id)
    outside = test_db.get(Workflow, input_workflow.workflow_id)
    stored_instance = test_db.get(Instance, input_instance.instance_id)
    assert claimed is not None and claimed.workflow_status == WorkflowStatus.FAILED
    assert outside is not None and outside.workflow_status == WorkflowStatus.COMPLETE
    assert stored_instance is not None and stored_instance.value == original_value


def test_annotation_runner_rejects_multi_workflow_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    first = _workflow(test_db, "First")
    second = _workflow(test_db, "Second")
    assert queue_fjob(test_db, JOB_ID, workflow_ids=(first.workflow_id, second.workflow_id))
    test_db.commit()

    with pytest.raises(ValueError, match="exactly its input workflow"):
        PythonAnnotationRunner(testing_session_local).execute(JOB_ID, _input(first))

    test_db.expire_all()
    stored_first = test_db.get(Workflow, first.workflow_id)
    stored_second = test_db.get(Workflow, second.workflow_id)
    assert stored_first is not None and stored_first.workflow_status == WorkflowStatus.FAILED
    assert stored_second is not None and stored_second.workflow_status == WorkflowStatus.FAILED


def test_annotation_runner_rejects_job_with_grouping(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    workflow = _workflow(test_db)
    function = FunctionDefinition(
        namespace="annotation-tests",
        function_name="grouping",
        function_definition={"name": "literalString", "value": "group", "mutable": False},
    )
    test_db.add(function)
    test_db.flush()
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function.function_definition_id,
        grouping_status=GroupingStatus.COMPLETE,
    )
    test_db.add(grouping)
    test_db.flush()
    assert queue_fjob(
        test_db,
        JOB_ID,
        workflow_ids=(workflow.workflow_id,),
        grouping_ids=(grouping.grouping_id,),
    )
    test_db.commit()

    with pytest.raises(ValueError, match="no groupings"):
        PythonAnnotationRunner(testing_session_local).execute(JOB_ID, _input(workflow))

    test_db.expire_all()
    stored_workflow = test_db.get(Workflow, workflow.workflow_id)
    stored_grouping = test_db.get(Grouping, grouping.grouping_id)
    assert stored_workflow is not None and stored_workflow.workflow_status == WorkflowStatus.FAILED
    assert stored_grouping is not None and stored_grouping.grouping_status == GroupingStatus.FAILED


def test_annotation_runner_ignores_stale_job(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    workflow = _workflow(test_db)
    instance = _instance(test_db, workflow)
    original_value = instance.value
    assert queue_fjob(test_db, JOB_ID, workflow_ids=(workflow.workflow_id,))
    test_db.commit()

    PythonAnnotationRunner(testing_session_local).execute(STALE_JOB_ID, _input(workflow))

    test_db.expire_all()
    stored_workflow = test_db.get(Workflow, workflow.workflow_id)
    stored_instance = test_db.get(Instance, instance.instance_id)
    assert stored_workflow is not None and stored_workflow.workflow_status == WorkflowStatus.PENDING
    assert stored_instance is not None and stored_instance.value == original_value
