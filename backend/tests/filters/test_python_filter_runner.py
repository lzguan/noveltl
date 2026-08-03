import uuid

import pytest
from sqlalchemy.orm import Session, sessionmaker

from src.filters.data_types import DataObj, FloatData, FloatField, Schema
from src.filters.functions import Get
from src.filters.models import FunctionDefinition, Instance, Workflow, WorkflowStatus
from src.filters.runners.python.filter_runner import PythonFilterInput, PythonFilterRunner
from src.schemas import Model

JOB_ID = uuid.UUID("e267c789-20e9-4eb0-b096-4200914c8e9b")


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def test_filter_runner_rejects_non_boolean_function(
    test_db: Session,
    testing_session_local: sessionmaker[Session],
) -> None:
    schema = Schema(fields={"score": FloatField()})
    source = Workflow(
        workflow_name="Filter source",
        schema=_dump(schema),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    output = Workflow(
        workflow_name="Filter output",
        schema=_dump(schema),
        job_id=JOB_ID,
    )
    function_definition = FunctionDefinition(
        namespace="test",
        function_name="invalid-filter",
        function_definition=_dump(Get(field_name="score", type="float")),
    )
    test_db.add_all([source, output, function_definition])
    test_db.flush()
    test_db.add(
        Instance(
            workflow_id=source.workflow_id,
            value=_dump(DataObj(fields={"score": FloatData(value=0.5)})),
        )
    )
    test_db.commit()

    with pytest.raises(ValueError, match="must return a boolean"):
        PythonFilterRunner(testing_session_local).execute(
            JOB_ID,
            PythonFilterInput(
                runner_name="filter",
                runtime_name="python",
                source_workflow_id=source.workflow_id,
                output_workflow_id=output.workflow_id,
                function_definition_id=function_definition.function_definition_id,
            ),
        )

    test_db.expire_all()
    stored_output = test_db.get(Workflow, output.workflow_id)
    assert stored_output is not None
    assert stored_output.workflow_status == WorkflowStatus.FAILED
