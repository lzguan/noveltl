from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, TypeAdapter, field_validator, model_validator

from src.filters.data_types import DataObj, FieldName, Schema
from src.filters.exceptions import InvalidSortKeyException, UnsupportedSortTypeException
from src.filters.functions import Signature, function_adapter
from src.filters.models import GroupingStatus, WorkflowStatus, WorkflowUseCase
from src.filters.runners.python.annotation_runner import NewFieldRequest
from src.filters.runners.python.group_runner import GroupData
from src.filters.runners.python.types import PythonRunnerInput
from src.schemas import Model

type RunnerInput = Annotated[PythonRunnerInput, Field(discriminator="runtime_name")]
runner_input_adapter = TypeAdapter(RunnerInput)


class GroupFilter(Model):
    grouping_id: UUID
    values: list[GroupData] = Field(max_length=100)


class FunctionDefinitionMeta(Model):
    function_definition_id: UUID
    namespace: str
    function_name: str


class FunctionDefinitionResponse(FunctionDefinitionMeta):
    model_config = ConfigDict(from_attributes=True)

    function_definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowSummary(Model):
    model_config = ConfigDict(from_attributes=True)

    workflow_id: UUID
    workflow_name: str | None
    use_case: WorkflowUseCase
    workflow_schema: Schema = Field(alias="schema")
    job_id: UUID | None
    workflow_status: WorkflowStatus
    workflow_message: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowResponse(Model):
    workflow_id: UUID
    workflow_name: str | None
    use_case: WorkflowUseCase
    workflow_schema: Schema = Field(alias="schema")
    job_id: UUID | None
    workflow_status: WorkflowStatus
    workflow_message: str | None
    novel_ids: list[UUID]
    label_group_ids: list[UUID]
    instance_count: int
    created_at: datetime
    updated_at: datetime


class GroupingSummary(Model):
    model_config = ConfigDict(from_attributes=True)

    grouping_id: UUID
    workflow_id: UUID
    function_definition_id: UUID
    job_id: UUID | None
    grouping_status: GroupingStatus
    grouping_message: str | None
    created_at: datetime
    updated_at: datetime


class GroupingResponse(Model):
    grouping_id: UUID
    workflow_id: UUID
    function_definition: FunctionDefinitionMeta
    output_type: Literal["string", "int", "bool"]
    job_id: UUID | None
    grouping_status: GroupingStatus
    grouping_message: str | None
    assignment_count: int
    created_at: datetime
    updated_at: datetime


class GroupValueCount(Model):
    value: GroupData
    count: int


class InstanceResponse(Model):
    model_config = ConfigDict(from_attributes=True)

    instance_id: UUID
    workflow_id: UUID
    value: DataObj


class InstanceQueryResult(Model):
    instance: InstanceResponse
    group_values: dict[UUID, GroupData]


class SortDirection(StrEnum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class SortKey(Model):
    field_name: FieldName
    direction: SortDirection


class Frame(Model):
    group_filters: list[GroupFilter] = Field(max_length=10)
    workflow_id: UUID
    sort_keys: list[SortKey] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_group_filters(self) -> Self:
        ids = set()
        for group_filter in self.group_filters:
            if group_filter.grouping_id in ids:
                raise ValueError(f"Duplicate grouping_id {group_filter.grouping_id} in frame")
            ids.add(group_filter.grouping_id)
        return self

    @model_validator(mode="after")
    def validate_sort_keys(self) -> Self:
        if len({sort_key.field_name for sort_key in self.sort_keys}) != len(self.sort_keys):
            raise ValueError("Duplicate sort keys are not allowed in a frame")
        return self


class InstanceQuery(Model):
    frame: Frame
    limit: int = Field(default=50, ge=1, le=100)
    cursor: UUID | None = Field(
        default=None,
        description="Cursor for pagination. If provided, must be a valid instance id. The query will return results after this cursor according to the sort keys.",
    )


RegistryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class FilterWriteRequest(Model):
    model_config = ConfigDict(extra="forbid")


class CreateFunctionDefinitionRequest(FilterWriteRequest):
    namespace: RegistryName
    function_name: RegistryName
    function_definition: dict[str, Any]

    @field_validator("function_definition")
    @classmethod
    def validate_function_definition(cls, value: dict[str, Any]) -> dict[str, Any]:
        function_adapter.validate_python(value)
        return value


class ValidateFunctionDefinitionRequest(FilterWriteRequest):
    function_definition: dict[str, Any]

    @field_validator("function_definition")
    @classmethod
    def validate_function_definition(cls, value: dict[str, Any]) -> dict[str, Any]:
        function_adapter.validate_python(value)
        return value


class FunctionDefinitionValidationResponse(Model):
    signature: Signature


class RenameWorkflowRequest(FilterWriteRequest):
    workflow_name: str | None = Field(max_length=100)


class PythonLabelSourceRequest(FilterWriteRequest):
    label_group_id: UUID = Field(description="Label group whose current labels will seed the workflow.")
    output_name: str | None = Field(default=None, max_length=100)


class PythonAnnotationRequest(FilterWriteRequest):
    workflow_id: UUID = Field(description="Completed workflow whose instances will receive the new fields.")
    new_fields: dict[FieldName, NewFieldRequest] = Field(min_length=1, max_length=100)


class PythonMapRequest(FilterWriteRequest):
    source_workflow_id: UUID = Field(description="Completed workflow whose instances will be mapped.")
    function_definition_id: UUID = Field(description="Saved object-to-object function to execute.")
    output_name: str | None = Field(default=None, max_length=100)


class PythonFilterRequest(FilterWriteRequest):
    source_workflow_id: UUID = Field(description="Completed workflow whose instances will be filtered.")
    function_definition_id: UUID = Field(description="Saved object-to-boolean function to execute.")
    output_name: str | None = Field(default=None, max_length=100)


class PythonGroupRequest(FilterWriteRequest):
    workflow_id: UUID = Field(description="Completed workflow whose instances will be grouped.")
    function_definition_id: UUID = Field(description="Saved object-to-scalar grouping function to execute.")


class WorkflowOperationAccepted(Model):
    job_id: UUID
    workflow: WorkflowResponse


class GroupOperationAccepted(Model):
    job_id: UUID
    grouping: GroupingResponse


def validate_frame_workflow(frame: Frame, schema: Schema):
    for sort_key in frame.sort_keys:
        if sort_key.field_name not in schema.fields:
            raise InvalidSortKeyException(f"Sort key {sort_key.field_name} is not a valid field in the schema")
        if schema.fields[sort_key.field_name].type not in ("string", "int", "bool", "float"):
            raise UnsupportedSortTypeException(
                f"Sort key {sort_key.field_name} must be of type string, int, bool, or float"
            )
