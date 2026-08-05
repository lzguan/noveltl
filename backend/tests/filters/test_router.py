import uuid
from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.filters.data_types import DataObj, IntData, IntField, Schema, StringData, StringField
from src.filters.functions import Get
from src.filters.models import (
    FunctionDefinition,
    GroupAssignment,
    Grouping,
    GroupingStatus,
    Instance,
    Workflow,
    WorkflowStatus,
)
from src.schemas import Model
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _dump(value: Model) -> dict[str, object]:
    return value.model_dump(mode="json", by_alias=True, exclude_computed_fields=True)


def _create_router_data(db: Session) -> tuple[Workflow, tuple[Instance, ...], Grouping, FunctionDefinition]:
    schema = Schema(fields={"name": StringField(), "score": IntField()})
    workflow = Workflow(
        workflow_name="Router workflow",
        schema=_dump(schema),
        workflow_status=WorkflowStatus.COMPLETE,
    )
    function_definition = FunctionDefinition(
        namespace="router",
        function_name="group-name",
        function_definition=_dump(Get(field_name="name", type="string")),
    )
    db.add_all([workflow, function_definition])
    db.flush()

    instances = tuple(
        Instance(
            instance_id=uuid.UUID(int=index),
            workflow_id=workflow.workflow_id,
            value=_dump(
                DataObj(
                    fields={
                        "name": StringData(value=name),
                        "score": IntData(value=score),
                    }
                )
            ),
        )
        for index, (name, score) in enumerate((("Alice", 2), ("Bob", 3), ("Alice", 1)), start=1)
    )
    grouping = Grouping(
        workflow_id=workflow.workflow_id,
        function_definition_id=function_definition.function_definition_id,
        grouping_status=GroupingStatus.COMPLETE,
    )
    db.add_all([*instances, grouping])
    db.flush()
    db.add_all(
        GroupAssignment(
            grouping_id=grouping.grouping_id,
            instance_id=instance.instance_id,
            function_value=name,
        )
        for instance, name in zip(instances, ("Alice", "Bob", "Alice"), strict=True)
    )
    db.commit()
    return workflow, instances, grouping, function_definition


def test_filter_read_endpoints_return_locked_contract(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    workflow, instances, grouping, function_definition = _create_router_data(test_db)
    headers = _auth_headers(sample_scenario.users["admin"])

    functions_response = client.get("/filters/functions?namespace=router", headers=headers)
    function_response = client.get(f"/filters/functions/{function_definition.function_definition_id}", headers=headers)
    workflows_response = client.get("/filters/workflows?search=Router&status=complete", headers=headers)
    workflow_response = client.get(f"/filters/workflows/{workflow.workflow_id}", headers=headers)
    first_instances_response = client.get(
        f"/filters/workflows/{workflow.workflow_id}/instances?limit=2", headers=headers
    )
    second_instances_response = client.get(
        f"/filters/workflows/{workflow.workflow_id}/instances?limit=2&cursor={instances[1].instance_id}",
        headers=headers,
    )
    groupings_response = client.get(f"/filters/workflows/{workflow.workflow_id}/groupings", headers=headers)
    grouping_response = client.get(f"/filters/groupings/{grouping.grouping_id}", headers=headers)
    values_response = client.get(f"/filters/groupings/{grouping.grouping_id}/values?search=Ali", headers=headers)
    advanced_response = client.post(
        "/filters/instances/query",
        headers=headers,
        json={
            "frame": {
                "workflowId": str(workflow.workflow_id),
                "groupFilters": [{"groupingId": str(grouping.grouping_id), "values": []}],
                "sortKeys": [{"fieldName": "score", "direction": "desc"}],
            },
            "limit": 2,
            "cursor": None,
        },
    )

    assert functions_response.status_code == status.HTTP_200_OK
    assert functions_response.json() == [
        {
            "functionDefinitionId": str(function_definition.function_definition_id),
            "namespace": "router",
            "functionName": "group-name",
        }
    ]
    assert function_response.status_code == status.HTTP_200_OK
    assert function_response.json()["functionDefinition"] == _dump(Get(field_name="name", type="string"))

    assert workflows_response.status_code == status.HTTP_200_OK
    workflow_summary = workflows_response.json()[0]
    assert workflow_summary["workflowId"] == str(workflow.workflow_id)
    assert workflow_summary["schema"] == _dump(Schema(fields={"name": StringField(), "score": IntField()}))
    assert "novelIds" not in workflow_summary
    assert workflow_response.status_code == status.HTTP_200_OK
    assert workflow_response.json()["instanceCount"] == 3
    assert workflow_response.json()["novelIds"] == []

    assert first_instances_response.status_code == status.HTTP_200_OK
    assert [entry["instanceId"] for entry in first_instances_response.json()] == [
        str(instances[0].instance_id),
        str(instances[1].instance_id),
    ]
    assert [entry["instanceId"] for entry in second_instances_response.json()] == [str(instances[2].instance_id)]

    assert groupings_response.status_code == status.HTTP_200_OK
    assert groupings_response.json()[0]["functionDefinitionId"] == str(function_definition.function_definition_id)
    assert "assignmentCount" not in groupings_response.json()[0]
    assert grouping_response.status_code == status.HTTP_200_OK
    assert grouping_response.json()["assignmentCount"] == 3
    assert grouping_response.json()["outputType"] == "string"
    assert values_response.status_code == status.HTTP_200_OK
    assert values_response.json() == [
        {"value": {"kind": "value", "type": "string", "value": "Alice"}, "count": 2}
    ]

    assert advanced_response.status_code == status.HTTP_200_OK
    advanced_payload = advanced_response.json()
    assert [entry["instance"]["instanceId"] for entry in advanced_payload] == [
        str(instances[1].instance_id),
        str(instances[0].instance_id),
    ]
    assert advanced_payload[0]["groupValues"][str(grouping.grouping_id)]["value"] == "Bob"


def test_filter_router_maps_permissions_readiness_and_invalid_query_errors(
    client: TestClient,
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    workflow, _, grouping, _ = _create_router_data(test_db)
    admin_headers = _auth_headers(sample_scenario.users["admin"])
    user_headers = _auth_headers(sample_scenario.users["user"])

    hidden = client.get(f"/filters/workflows/{workflow.workflow_id}", headers=user_headers)
    invalid_query = client.post(
        "/filters/instances/query",
        headers=admin_headers,
        json={
            "frame": {
                "workflowId": str(workflow.workflow_id),
                "groupFilters": [{"groupingId": str(grouping.grouping_id), "values": []}],
                "sortKeys": [{"fieldName": "missing", "direction": "asc"}],
            }
        },
    )
    workflow.workflow_status = WorkflowStatus.PROCESSING
    test_db.commit()
    not_ready = client.get(f"/filters/workflows/{workflow.workflow_id}/instances", headers=admin_headers)
    invalid_limit = client.get("/filters/workflows?limit=101", headers=admin_headers)

    assert hidden.status_code == status.HTTP_404_NOT_FOUND
    assert invalid_query.status_code == status.HTTP_400_BAD_REQUEST
    assert not_ready.status_code == status.HTTP_409_CONFLICT
    assert invalid_limit.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_filter_openapi_exposes_locked_read_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    assert "/filters/functions" in paths
    assert "/filters/functions/{functionDefinitionId}" in paths
    assert "/filters/workflows" in paths
    assert "/filters/workflows/{workflowId}" in paths
    assert "/filters/workflows/{workflowId}/instances" in paths
    assert "/filters/instances/query" in paths
    assert "/filters/workflows/{workflowId}/groupings" in paths
    assert "/filters/groupings/{groupingId}" in paths
    assert "/filters/groupings/{groupingId}/values" in paths
    assert "/filters/workflows/{workflowId}/instances/query" not in paths

    operation = paths["/filters/instances/query"]["post"]
    body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert body_schema["$ref"].endswith("/InstanceQuery")
