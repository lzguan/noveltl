from datetime import timedelta
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.filters.data_types import BoolField, Schema, StringField
from src.filters.exceptions import RunnerEnqueueFailedException
from src.filters.functions import Extend, Get, LiteralString
from src.filters.models import (
    FunctionDefinition,
    Workflow,
    WorkflowLabelGroup,
    WorkflowNovel,
    WorkflowStatus,
)
from src.schemas import Model
from test_support.filters import RecordingRunnerDispatcher
from test_support.test_data.scenarios import DatabaseScenario


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def dump_model(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def add_scoped_workflow(
    db: Session,
    scenario: DatabaseScenario,
    schema: Schema,
    *,
    workflow_status: WorkflowStatus = WorkflowStatus.COMPLETE,
) -> Workflow:
    workflow = Workflow(schema=dump_model(schema), workflow_status=workflow_status)
    db.add(workflow)
    db.flush()
    db.add_all(
        [
            WorkflowNovel(
                workflow_id=workflow.workflow_id,
                novel_id=scenario.novels["novel_1"].novel_id,
            ),
            WorkflowLabelGroup(
                workflow_id=workflow.workflow_id,
                label_group_id=scenario.label_groups["official"].label_group_id,
            ),
        ]
    )
    db.commit()
    return workflow


def add_function(db: Session, name: str, function: Model) -> FunctionDefinition:
    definition = FunctionDefinition(
        namespace="router-write",
        function_name=name,
        function_definition=dump_model(function),
    )
    db.add(definition)
    db.commit()
    return definition


def test_write_routes_return_operation_specific_success_responses(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
) -> None:
    headers = auth_headers(sample_scenario.users["admin"])
    source_schema = Schema(fields={"name": StringField(), "active": BoolField()})
    source = add_scoped_workflow(test_db, sample_scenario, source_schema)
    map_function = add_function(
        test_db,
        "map",
        Extend(input_schema=source_schema, fields={"extra": LiteralString(value="x")}),
    )
    filter_function = add_function(test_db, "filter", Get(field_name="active", type="bool"))
    group_function = add_function(test_db, "group", Get(field_name="name", type="string"))

    function_response = client.post(
        "/filters/functions",
        headers=headers,
        json={
            "namespace": "created",
            "functionName": "literal",
            "functionDefinition": {"name": "literalString", "value": "Alice"},
        },
    )
    rename_response = client.patch(
        f"/filters/workflows/{source.workflow_id}",
        headers=headers,
        json={"workflowName": "Source"},
    )
    label_response = client.post(
        "/filters/runners/python/label-source",
        headers=headers,
        json={
            "labelGroupId": str(sample_scenario.label_groups["official"].label_group_id),
            "outputName": "Labels",
        },
    )
    map_response = client.post(
        "/filters/runners/python/map",
        headers=headers,
        json={
            "sourceWorkflowId": str(source.workflow_id),
            "functionDefinitionId": str(map_function.function_definition_id),
            "outputName": "Mapped",
        },
    )
    filter_response = client.post(
        "/filters/runners/python/filter",
        headers=headers,
        json={
            "sourceWorkflowId": str(source.workflow_id),
            "functionDefinitionId": str(filter_function.function_definition_id),
            "outputName": "Filtered",
        },
    )
    group_response = client.post(
        "/filters/runners/python/group",
        headers=headers,
        json={
            "workflowId": str(source.workflow_id),
            "functionDefinitionId": str(group_function.function_definition_id),
        },
    )

    assert function_response.status_code == status.HTTP_201_CREATED
    assert function_response.json()["functionName"] == "literal"
    assert rename_response.status_code == status.HTTP_200_OK
    assert rename_response.json()["workflowName"] == "Source"
    for response in (label_response, map_response, filter_response):
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["jobId"] == response.json()["workflow"]["jobId"]
    assert group_response.status_code == status.HTTP_202_ACCEPTED
    assert group_response.json()["jobId"] == group_response.json()["grouping"]["jobId"]
    assert len(recording_runner_dispatcher.jobs) == 4


def test_validate_function_returns_signature_without_persisting(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    function_ids_before = set(test_db.scalars(select(FunctionDefinition.function_definition_id)))

    response = client.post(
        "/filters/functions/validate",
        headers=auth_headers(sample_scenario.users["admin"]),
        json={
            "functionDefinition": {"name": "literalString", "value": "Alice"},
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "signature": {
            "args": [],
            "output": {"obj": False, "type": "string", "mutable": False},
        }
    }
    assert set(test_db.scalars(select(FunctionDefinition.function_definition_id))) == function_ids_before


def test_write_routes_map_missing_resources_to_404(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
) -> None:
    headers = auth_headers(sample_scenario.users["admin"])
    workflow = add_scoped_workflow(
        test_db,
        sample_scenario,
        Schema(fields={"name": StringField()}),
    )

    missing_workflow = client.post(
        "/filters/runners/python/map",
        headers=headers,
        json={
            "sourceWorkflowId": str(uuid4()),
            "functionDefinitionId": str(uuid4()),
        },
    )
    missing_function = client.post(
        "/filters/runners/python/group",
        headers=headers,
        json={
            "workflowId": str(workflow.workflow_id),
            "functionDefinitionId": str(uuid4()),
        },
    )
    inaccessible_label_group = client.post(
        "/filters/runners/python/label-source",
        headers=auth_headers(sample_scenario.users["user"]),
        json={"labelGroupId": str(sample_scenario.label_groups["official"].label_group_id)},
    )

    assert missing_workflow.status_code == status.HTTP_404_NOT_FOUND
    assert missing_function.status_code == status.HTTP_404_NOT_FOUND
    assert inaccessible_label_group.status_code == status.HTTP_404_NOT_FOUND
    assert recording_runner_dispatcher.jobs == []


def test_write_routes_distinguish_invalid_request_and_state_conflict(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
) -> None:
    headers = auth_headers(sample_scenario.users["admin"])
    schema = Schema(fields={"name": StringField()})
    complete = add_scoped_workflow(test_db, sample_scenario, schema)
    pending = add_scoped_workflow(
        test_db,
        sample_scenario,
        schema,
        workflow_status=WorkflowStatus.PENDING,
    )
    string_function = add_function(test_db, "string", Get(field_name="name", type="string"))
    map_function = add_function(
        test_db,
        "pending-map",
        Extend(input_schema=schema, fields={"extra": LiteralString(value="x")}),
    )

    invalid_filter = client.post(
        "/filters/runners/python/filter",
        headers=headers,
        json={
            "sourceWorkflowId": str(complete.workflow_id),
            "functionDefinitionId": str(string_function.function_definition_id),
        },
    )
    pending_map = client.post(
        "/filters/runners/python/map",
        headers=headers,
        json={
            "sourceWorkflowId": str(pending.workflow_id),
            "functionDefinitionId": str(map_function.function_definition_id),
        },
    )
    first_group = client.post(
        "/filters/runners/python/group",
        headers=headers,
        json={
            "workflowId": str(complete.workflow_id),
            "functionDefinitionId": str(string_function.function_definition_id),
        },
    )
    duplicate_group = client.post(
        "/filters/runners/python/group",
        headers=headers,
        json={
            "workflowId": str(complete.workflow_id),
            "functionDefinitionId": str(string_function.function_definition_id),
        },
    )

    assert invalid_filter.status_code == status.HTTP_400_BAD_REQUEST
    assert pending_map.status_code == status.HTTP_409_CONFLICT
    assert first_group.status_code == status.HTTP_202_ACCEPTED
    assert duplicate_group.status_code == status.HTTP_409_CONFLICT
    assert len(recording_runner_dispatcher.jobs) == 1


def test_runner_publication_failure_returns_503_and_persists_failed_target(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
) -> None:
    recording_runner_dispatcher.enqueue_error = RunnerEnqueueFailedException("broker unavailable")

    response = client.post(
        "/filters/runners/python/label-source",
        headers=auth_headers(sample_scenario.users["admin"]),
        json={
            "labelGroupId": str(sample_scenario.label_groups["official"].label_group_id),
            "outputName": "Failed publication",
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    workflow = test_db.execute(select(Workflow).where(Workflow.workflow_name == "Failed publication")).scalar_one()
    assert workflow.workflow_status == WorkflowStatus.FAILED
    assert recording_runner_dispatcher.jobs == []


def test_write_request_validation_and_openapi_contract(
    client: TestClient,
    sample_scenario: DatabaseScenario,
) -> None:
    headers = auth_headers(sample_scenario.users["admin"])
    invalid_ast = client.post(
        "/filters/functions",
        headers=headers,
        json={
            "namespace": "invalid",
            "functionName": "invalid",
            "functionDefinition": {"name": "not-a-function"},
        },
    )
    invalid_draft = client.post(
        "/filters/functions/validate",
        headers=headers,
        json={"functionDefinition": {"name": "not-a-function"}},
    )
    unauthenticated_draft = client.post(
        "/filters/functions/validate",
        json={"functionDefinition": {"name": "literalString", "value": "Alice"}},
    )
    empty_rename = client.patch(
        f"/filters/workflows/{uuid4()}",
        headers=headers,
        json={},
    )
    internal_runner_fields = client.post(
        "/filters/runners/python/label-source",
        headers=headers,
        json={
            "labelGroupId": str(sample_scenario.label_groups["official"].label_group_id),
            "runnerName": "ls",
        },
    )
    openapi = client.get("/openapi.json").json()

    assert invalid_ast.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert invalid_draft.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert unauthenticated_draft.status_code == status.HTTP_401_UNAUTHORIZED
    assert empty_rename.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert internal_runner_fields.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    expected_operations = {
        "/filters/functions/validate": (
            "post",
            "validate_filter_function",
            "ValidateFunctionDefinitionRequest",
        ),
        "/filters/functions": ("post", "create_filter_function", "CreateFunctionDefinitionRequest"),
        "/filters/workflows/{workflowId}": ("patch", "rename_filter_workflow", "RenameWorkflowRequest"),
        "/filters/runners/python/label-source": (
            "post",
            "run_python_label_source",
            "PythonLabelSourceRequest",
        ),
        "/filters/runners/python/map": ("post", "run_python_map", "PythonMapRequest"),
        "/filters/runners/python/filter": ("post", "run_python_filter", "PythonFilterRequest"),
        "/filters/runners/python/group": ("post", "run_python_group", "PythonGroupRequest"),
    }
    request_schemas = set()
    for path, (method, operation_id, schema_name) in expected_operations.items():
        operation = openapi["paths"][path][method]
        assert operation["operationId"] == operation_id
        schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert schema_ref.endswith(f"/{schema_name}")
        request_schemas.add(schema_ref)
    assert len(request_schemas) == len(expected_operations)
    map_properties = openapi["components"]["schemas"]["PythonMapRequest"]["properties"]
    assert map_properties["sourceWorkflowId"]["description"]
    assert map_properties["functionDefinitionId"]["description"]
